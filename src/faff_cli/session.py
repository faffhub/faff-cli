import typer
from typing import List, Optional
from faff_core import Workspace, Filter, query_sessions
from faff_cli.output import create_formatter
from faff_cli.filtering import FilterConfig, apply_filters
import datetime
import humanize
from rich.table import Table
from rich.console import Console

app = typer.Typer(help="View and analyze time tracking sessions.")

def format_duration(td: datetime.timedelta) -> str:
    """Format timedelta as hours and minutes."""
    total_minutes = int(td.total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)

@app.command(name="list")
def list_sessions(
    ctx: typer.Context,
    filter_strings: List[str] = typer.Argument(
        None,
        help="Filters: field=value (exact), field~value (contains), field!=value (not equal)",
    ),
    from_date: Optional[str] = typer.Option(
        None,
        "--from", "-f",
        help="Start date (inclusive), e.g., 2025-01-01 or 'last monday'",
    ),
    to_date: Optional[str] = typer.Option(
        None,
        "--to", "-t",
        help="End date (inclusive), e.g., 2025-01-31 or 'today'",
    ),
    since: Optional[str] = typer.Option(
        None,
        "--since",
        help="Start date onwards (shortcut for --from with open end)",
    ),
    until: Optional[str] = typer.Option(
        None,
        "--until",
        help="Up to date (shortcut for --to with open start)",
    ),
    limit: Optional[int] = typer.Option(
        None,
        "--limit", "-n",
        help="Limit number of results",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    plain_output: bool = typer.Option(
        False,
        "--plain",
        help="Output as plain text (no colors)",
    ),
):
    """
    List all individual sessions.

    Shows each session as a separate row with date, intent, duration, and reflection.
    Supports filtering by ASTRO fields and date ranges.

    Examples:
        faff session list
        faff session list --from 2025-01-01 --to 2025-01-31
        faff session list alias~meeting
        faff session list role=consultant --since last-monday
        faff session list --json
    """
    try:
        ws: Workspace = ctx.obj

        # Parse filters and dates
        filter_config = FilterConfig(
            filter_strings=filter_strings,
            from_date=from_date,
            to_date=to_date,
            since=since,
            until=until,
        )
        filters, resolved_from, resolved_to = filter_config.get_all(ws)

        # Get all logs
        logs = ws.logs.list_logs()

        # Build session data
        session_data = []
        for log in logs:
            # Apply date range filter at log level
            if resolved_from and log.date < resolved_from:
                continue
            if resolved_to and log.date > resolved_to:
                continue

            for session in log.timeline:
                # Calculate duration
                if session.end is None:
                    duration = session.elapsed(ws.now())
                else:
                    duration = session.duration

                session_data.append({
                    "date": str(log.date),
                    "date_obj": log.date,
                    "start": session.start.strftime("%H:%M:%S"),
                    "end": session.end.strftime("%H:%M:%S") if session.end else "active",
                    "alias": session.intent.alias,
                    "role": session.intent.role or "",
                    "objective": session.intent.objective or "",
                    "action": session.intent.action or "",
                    "subject": session.intent.subject or "",
                    "trackers": ",".join(session.intent.trackers) if session.intent.trackers else "",
                    "duration": humanize.precisedelta(duration, minimum_unit="minutes"),
                    "duration_seconds": duration.total_seconds(),
                    "reflection": f"{session.reflection_score:.1f}" if session.reflection_score is not None else "",
                    "note": session.note or "",
                })

        # Apply filters
        if filters:
            session_data = apply_filters(session_data, filters)

        # Sort by date and time
        session_data.sort(key=lambda x: (x["date_obj"], x["start"]), reverse=False)

        # Apply limit
        if limit:
            session_data = session_data[:limit]

        # Create output formatter
        formatter = create_formatter(json_output, plain_output)

        # Define columns for table output
        columns = [
            ("date", "Date", "cyan"),
            ("start", "Start", None),
            ("end", "End", None),
            ("alias", "Intent", "yellow"),
            ("duration", "Duration", "green"),
            ("reflection", "Reflection", "blue"),
        ]

        # Output results
        formatter.print_table(
            session_data,
            columns,
            title="Sessions",
            total_label="session(s)" if session_data else None,
        )

        if not session_data and not json_output:
            formatter.print_message("No sessions found matching criteria.", "yellow")

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error listing sessions: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)

@app.command()
def report(
    ctx: typer.Context,
    filter_strings: List[str] = typer.Argument(
        None,
        help="Filters in the form key=value, key~value, or key!=value (e.g. role=consultant).",
    ),
    group: Optional[str] = typer.Option(
        None,
        "--group", "-g",
        help="Field to group by (e.g. date, role, objective, subject, alias).",
    ),
    from_date: Optional[str] = typer.Option(
        None,
        "--from", "-f",
        help="Start date (inclusive), e.g. 2025-10-01.",
    ),
    to_date: Optional[str] = typer.Option(
        None,
        "--to", "-t",
        help="End date (inclusive), e.g. 2025-10-07.",
    ),
    since: Optional[str] = typer.Option(
        None,
        "--since",
        help="Shortcut for --from <date> with open end (mutually exclusive with --from).",
    ),
    until: Optional[str] = typer.Option(
        None,
        "--until",
        help="Shortcut for --to <date> with open start (mutually exclusive with --to).",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output results as JSON.",
    ),
    sum_only: bool = typer.Option(
        False,
        "--sum",
        help="Print only the total duration.",
    ),
):
    """
    Generate aggregated reports from sessions.

    Groups sessions by ASTRO fields and shows total duration for each group.
    This is the command you want for answering "how much time did I spend on X?"

    Examples:
        faff session report role=consultant
        faff session report alias~meeting --from 2025-01-01
        faff session report --since last-monday
        faff session report objective=alignment --sum
    """
    try:
        ws = ctx.obj

        # Validate mutually exclusive options
        if from_date and since:
            typer.echo("Error: --from and --since are mutually exclusive.")
            raise typer.Exit(code=1)
        if to_date and until:
            typer.echo("Error: --to and --until are mutually exclusive.")
            raise typer.Exit(code=1)

        # Resolve date range
        if since:
            from_date = since
        if until:
            to_date = until

        resolved_from_date = ws.parse_natural_date(from_date) if from_date else None
        resolved_to_date = ws.parse_natural_date(to_date) if to_date else None

        filters = [Filter.parse(f) for f in filter_strings] if filter_strings else []

        # Get all logs
        logs = ws.logs.list_logs()

        # Call Rust query_sessions - it returns dict with tuple keys and i64 values (seconds)
        results = query_sessions(logs, filters, resolved_from_date, resolved_to_date)

        # Convert seconds back to timedelta for Python
        summed_rows = {
            key: datetime.timedelta(seconds=duration_seconds)
            for key, duration_seconds in results.items()
        }

        # Calculate total
        total_duration = sum(summed_rows.values(), datetime.timedelta())

        # Handle sum-only mode or no filters (just show total)
        if sum_only or not filters:
            typer.echo(format_duration(total_duration))
            return

        # Display matches
        console = Console()
        table = Table()
        for filter in filters:
            table.add_column(filter.field().capitalize())
        table.add_column("Duration", justify="right")

        summed_rows = dict(sorted(summed_rows.items(), key=lambda item: item[1], reverse=True))

        for summed_row in summed_rows:
            table.add_row(*summed_row, format_duration(summed_rows[summed_row]))

        table.add_section()
        table.add_row("TOTAL", *["" for _ in range(len(filters) - 1)], format_duration(total_duration))

        console.print(table)

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error generating report: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)

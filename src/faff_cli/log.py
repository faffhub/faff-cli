import typer

from typing import List, Optional

from faff_cli.output import create_formatter
from faff_cli.filtering import FilterConfig, apply_filters, apply_date_range

from faff_core import Workspace

# Removed: PrivateLogFormatter (now using Rust formatter via log.to_log_file())
from faff_cli.utils import edit_file
from pathlib import Path

from typing import Dict
import datetime
import humanize

app = typer.Typer(help="View, edit, and interact with private logs.")

"""
faff log
faff log edit
faff log refresh
"""

@app.command()
def show(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    cli: faff log
    Show the log for today.
    """
    try:
        ws = ctx.obj
        resolved_date = ws.parse_natural_date(date)

        log = ws.logs.get_log(resolved_date)
        typer.echo(log.to_log_file(ws.plans.get_trackers(log.date)))
    except Exception as e:
        typer.echo(f"Error showing log: {e}", err=True)
        raise typer.Exit(1)

@app.command(name="list")  # To avoid conflict with list type
def log_list(
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
    List logs across all dates.

    Supports filtering by various fields and date ranges.
    Shows date, day of week, duration, session count, and status.

    Examples:
        faff log list
        faff log list --from 2025-01-01 --to 2025-01-31
        faff log list --since last-monday
        faff log list status=unclosed
        faff log list --json
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

        # Convert logs to dictionaries for filtering
        log_data = []
        for log in logs:
            is_closed = log.is_closed()
            total_time = log.total_recorded_time()
            session_count = len(log.timeline)

            # Calculate reflection score if any sessions have reflections
            reflection_scores = [s.reflection_score for s in log.timeline if s.reflection_score is not None]
            has_reflections = len(reflection_scores) > 0
            mean_reflection = (sum(reflection_scores) / len(reflection_scores)) if reflection_scores else None

            # Format status (no emojis)
            status_display = "closed" if is_closed else "unclosed"

            log_data.append({
                "date": str(log.date),
                "date_obj": log.date,  # For sorting
                "day": log.date.strftime("%a").upper(),
                "duration": humanize.precisedelta(total_time, minimum_unit="minutes"),
                "duration_seconds": total_time.total_seconds(),  # For filtering
                "sessions": session_count,
                "status": status_display,
                "status_value": "closed" if is_closed else "unclosed",  # For filtering
                "has_reflections": has_reflections,
                "mean_reflection": f"{mean_reflection:.1f}" if mean_reflection else "",
            })

        # Apply date range filter
        if resolved_from or resolved_to:
            log_data = apply_date_range(log_data, "date_obj", resolved_from, resolved_to)

        # Apply other filters
        if filters:
            log_data = apply_filters(log_data, filters)

        # Sort by date ascending (chronological order - oldest to newest)
        log_data.sort(key=lambda x: x["date_obj"], reverse=False)

        # Apply limit
        if limit:
            log_data = log_data[:limit]

        # Create output formatter
        formatter = create_formatter(json_output, plain_output)

        # Define columns for table output
        columns = [
            ("date", "Date", "cyan"),
            ("day", "Day", None),
            ("duration", "Duration", "green"),
            ("sessions", "Sessions", None),
            ("mean_reflection", "Reflection", "yellow"),
            ("status", "Status", None),
        ]

        # Output results
        formatter.print_table(
            log_data,
            columns,
            title="Logs",
            total_label="logs" if log_data else None,
        )

        if not log_data and not json_output:
            formatter.print_message("No logs found matching criteria.", "yellow")

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error listing logs: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)

@app.command()
def rm(ctx: typer.Context,
       date: str = typer.Argument(None),
       yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt")):
    """
    cli: faff log rm
    Remove the log for the specified date, defaulting to today.
    """
    ws: Workspace = ctx.obj
    resolved_date = ws.parse_natural_date(date)

    # Check if log exists
    if not ws.logs.log_exists(resolved_date):
        typer.echo(f"No log found for {resolved_date}.")
        raise typer.Exit(1)

    # Get the log to check if it's empty
    log = ws.logs.get_log(resolved_date)

    # Prompt for confirmation if log has content and --yes not specified
    if log and len(log.timeline) > 0 and not yes:
        session_count = len(log.timeline)
        total_time = humanize.precisedelta(log.total_recorded_time(), minimum_unit='minutes')

        typer.echo(f"Log for {resolved_date} contains {session_count} session(s) with {total_time} recorded.")
        confirm = typer.confirm("Are you sure you want to delete this log?")
        if not confirm:
            typer.echo("Deletion cancelled.")
            raise typer.Exit(0)

    # Delete the log
    try:
        ws.logs.delete_log(resolved_date)
        typer.echo(f"Log for {resolved_date} removed.")
    except Exception as e:
        typer.echo(f"Failed to delete log: {e}")
        raise typer.Exit(1)

@app.command()
def edit(ctx: typer.Context,
         date: str = typer.Argument(None),
         skip_validation: bool = typer.Option(False, "--force")):
    """
    cli: faff log edit
    Edit the log for the specified date, defaulting to today, in your default editor.
    """
    try:
        ws = ctx.obj

        resolved_date = ws.parse_natural_date(date)

        # Process the log to ensure it's correctly formatted for reading
        if not skip_validation:
            log = ws.logs.get_log(resolved_date)
            trackers = ws.plans.get_trackers(resolved_date)
            ws.logs.write_log(log, trackers)

        if edit_file(Path(ws.logs.log_file_path(resolved_date))):
            typer.echo("Log file updated.")

            # Process the edited file again after editing
            if not skip_validation:
                log = ws.logs.get_log(resolved_date)
                trackers = ws.plans.get_trackers(resolved_date)
                ws.logs.write_log(log, trackers)
        else:
            typer.echo("No changes detected.")
    except Exception as e:
        typer.echo(f"Error editing log: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def summary(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    cli: faff log summary
    Show a summary of the log for today.
    """
    ws: Workspace = ctx.obj
    resolved_date: datetime.date = ws.parse_natural_date(date)

    log = ws.logs.get_log(resolved_date)
    trackers = ws.plans.get_trackers(log.date)

    # Get summary from Rust core
    stats = log.summary(ws.now())

    # Format the summary (display logic stays in CLI)
    output = f"Summary for {resolved_date.isoformat()}:\n"
    output += f"\nTotal recorded time: {humanize.precisedelta(datetime.timedelta(minutes=stats['total_minutes']), minimum_unit='minutes')}\n"

    if stats['mean_reflection_score'] is not None:
        output += f"Mean reflection score: {stats['mean_reflection_score']:.2f}/5\n"

    output += "\nIntent Totals:\n"
    for alias, minutes in stats['by_intent'].items():
        output += f"- {alias}: {humanize.precisedelta(datetime.timedelta(minutes=minutes), minimum_unit='minutes')}\n"

    output += "\nTracker Totals:\n"
    for tracker, minutes in stats['by_tracker'].items():
        output += f"- {tracker} - {trackers.get(tracker)}: {humanize.precisedelta(datetime.timedelta(minutes=minutes), minimum_unit='minutes')}\n"

    output += "\nTracker Source Totals:\n"
    for source, minutes in stats['by_tracker_source'].items():
        output += f"- {source}: {humanize.precisedelta(datetime.timedelta(minutes=minutes), minimum_unit='minutes')}\n"

    typer.echo(output)

@app.command()
def refresh(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    cli: faff log refresh
    Reformat the log file.
    """
    try:
        ws = ctx.obj
        resolved_date = ws.parse_natural_date(date)

        log = ws.logs.get_log(resolved_date)
        trackers = ws.plans.get_trackers(resolved_date)
        ws.logs.write_log(log, trackers)
        typer.echo("Log refreshed.")
    except Exception as e:
        typer.echo(f"Error refreshing log: {e}", err=True)
        raise typer.Exit(1)
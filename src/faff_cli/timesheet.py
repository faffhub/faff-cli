import typer
import datetime
from typing import List, Optional

from faff_core import Workspace
from faff_cli.output import create_formatter
from faff_cli.filtering import FilterConfig, apply_filters, apply_date_range, parse_simple_filters


app = typer.Typer(help="Manage timesheets.")

@app.command()
def audiences(ctx: typer.Context):
    """
    List configured timesheet audiences.
    """
    ws: Workspace = ctx.obj

    audiences = ws.timesheets.audiences()
    typer.echo(f"Found {len(audiences)} configured audience(s):")
    for audience in audiences:
        typer.echo(f"- {audience.id} {audience.__class__.__name__}")
    
@app.command()
def compile(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    Compile the timesheet for a given date, defaulting to today.
    """
    ws: Workspace = ctx.obj
    resolved_date = ws.parse_natural_date(date)
    
    log = ws.logs.get_log(resolved_date)

    audiences = ws.timesheets.audiences()
    for audience in audiences:
        compiled_timesheet = ws.timesheets.compile(log, audience)

        # Sign the timesheet if signing_ids are configured
        signing_ids = audience.config.get('signing_ids', [])
        is_empty = len(compiled_timesheet.timeline) == 0

        if signing_ids:
            try:
                signed_timesheet = ws.timesheets.sign_timesheet(compiled_timesheet, signing_ids)
                ws.timesheets.write_timesheet(signed_timesheet)
                if is_empty:
                    typer.echo(f"Compiled and signed empty timesheet for {resolved_date} using {audience.id} (no relevant sessions).")
                else:
                    typer.echo(f"Compiled and signed timesheet for {resolved_date} using {audience.id}.")
            except Exception as e:
                # Signing failed - write unsigned and warn
                ws.timesheets.write_timesheet(compiled_timesheet)
                if is_empty:
                    typer.echo(f"Warning: Compiled unsigned empty timesheet for {resolved_date} using {audience.id} (signing failed: {e})", err=True)
                else:
                    typer.echo(f"Warning: Compiled unsigned timesheet for {resolved_date} using {audience.id} (signing failed: {e})", err=True)
        else:
            ws.timesheets.write_timesheet(compiled_timesheet)
            if is_empty:
                typer.echo(f"Warning: Compiled unsigned empty timesheet for {resolved_date} using {audience.id} (no signing_ids configured)", err=True)
            else:
                typer.echo(f"Warning: Compiled unsigned timesheet for {resolved_date} using {audience.id} (no signing_ids configured)", err=True)

@app.command(name="list") # To avoid conflict with list type
def list_timesheets(
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
    List generated timesheets.

    Supports filtering by various fields and date ranges.
    Shows audience, date, compilation time, and submission status.

    Examples:
        faff timesheet list
        faff timesheet list --from 2025-01-01 --to 2025-01-31
        faff timesheet list --since last-monday
        faff timesheet list audience=element
        faff timesheet list status~submitted
        faff timesheet list --json
    """
    try:
        ws: Workspace = ctx.obj

        # Parse filters using Python-side parsing (no Rust validation needed for display)
        filters = []
        if filter_strings:
            try:
                filters = parse_simple_filters(filter_strings)
            except ValueError as e:
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(1)

        # Parse dates using FilterConfig
        filter_config = FilterConfig(
            filter_strings=[],  # Don't parse filters with Rust
            from_date=from_date,
            to_date=to_date,
            since=since,
            until=until,
        )
        _, resolved_from, resolved_to = filter_config.get_all(ws)

        # Get all timesheets
        timesheets = ws.timesheets.list_timesheets()

        # Convert timesheets to dictionaries for filtering
        timesheet_data = []
        for ts in timesheets:
            # Parse the date for filtering
            if isinstance(ts.date, str):
                date_obj = datetime.date.fromisoformat(ts.date)
            else:
                date_obj = ts.date

            # Determine submission status from actual submission_status field
            submission_status = getattr(ts.meta, 'submission_status', None)
            submission_error = getattr(ts.meta, 'submission_error', None)

            # Map status
            if submission_status == "success":
                is_success = True
                is_failed = False
            elif submission_status == "failed":
                is_success = False
                is_failed = True
            else:
                # No status set - check if submitted_at exists (legacy behavior)
                is_success = ts.meta.submitted_at is not None
                is_failed = False

            # Format status based on output mode
            if json_output or plain_output:
                if is_failed:
                    status_display = "failed"
                elif is_success:
                    status_display = "submitted"
                else:
                    status_display = "pending"
            else:
                # Use colors in Rich mode
                if is_failed:
                    status_display = "[red]failed[/red]"
                elif is_success:
                    status_display = "[green]submitted[/green]"
                else:
                    status_display = "[yellow]pending[/yellow]"

            # Format timestamps
            if isinstance(ts.compiled, datetime.datetime):
                compiled_str = ts.compiled.strftime("%Y-%m-%d %H:%M:%S")
            else:
                compiled_str = str(ts.compiled)

            if is_success:
                if isinstance(ts.meta.submitted_at, datetime.datetime):
                    submitted_str = ts.meta.submitted_at.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    submitted_str = str(ts.meta.submitted_at)
            else:
                submitted_str = ""

            timesheet_data.append({
                "audience": ts.meta.audience_id,  # Match the column header
                "date": str(date_obj),
                "date_obj": date_obj,  # For sorting
                "compiled": compiled_str,
                "status": status_display,  # Match the column header
                "submitted_at": submitted_str,
            })

        # Apply date range filter
        if resolved_from or resolved_to:
            timesheet_data = apply_date_range(timesheet_data, "date_obj", resolved_from, resolved_to)

        # Apply other filters
        if filters:
            timesheet_data = apply_filters(timesheet_data, filters)

        # Sort by date ascending (chronological order - oldest to newest)
        timesheet_data.sort(key=lambda x: x["date_obj"], reverse=False)

        # Apply limit
        if limit:
            timesheet_data = timesheet_data[:limit]

        # Create output formatter
        formatter = create_formatter(json_output, plain_output)

        # Define columns for table output
        columns = [
            ("audience", "Audience", "cyan"),
            ("date", "Date", "cyan"),
            ("compiled", "Compiled", None),
            ("status", "Status", None),
        ]

        # Add submitted_at column only if not in JSON mode (JSON will include all fields)
        if not json_output and any(ts["submitted_at"] for ts in timesheet_data):
            columns.append(("submitted_at", "Submitted At", "green"))

        # Output results
        formatter.print_table(
            timesheet_data,
            columns,
            title="Timesheets",
            total_label="timesheets" if timesheet_data else None,
        )

        if not timesheet_data and not json_output:
            formatter.print_message("No timesheets found matching criteria.", "yellow")

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error listing timesheets: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)

@app.command()
def show(ctx: typer.Context, audience_id: str, date: str = typer.Argument(None), pretty: bool = typer.Option(
        False,
        "--pretty",
        help="Pretty-print the output instead of canonical JSON (without whitespace)",
    )):
    ws: Workspace = ctx.obj
    resolved_date = ws.parse_natural_date(date)

    timesheet = ws.timesheets.get_timesheet(audience_id, resolved_date)
    import json
    if timesheet:
        data = json.loads(timesheet.submittable_timesheet().canonical_form().decode("utf-8"))
        if pretty:
            typer.echo(json.dumps(data, indent=2))
        else:
            typer.echo(data)

@app.command()
def submit(ctx: typer.Context, audience_id: str, date: str = typer.Argument(None)):
    """
    Push the timesheet for a given date, defaulting to today.
    """
    ws: Workspace = ctx.obj
    resolved_date = ws.parse_natural_date(date)

    timesheet = ws.timesheets.get_timesheet(audience_id, resolved_date)
    if timesheet:
        ws.timesheets.submit(timesheet)

@app.command()
def rm(
    ctx: typer.Context,
    date: str = typer.Argument(None, help="Date of timesheet to delete (defaults to today)"),
    audience_id: Optional[str] = typer.Option(None, "--audience", "-a", help="Specific audience to delete (defaults to all)"),
):
    """
    Delete compiled timesheet(s) for a given date.

    By default, deletes timesheets for all audiences. Use --audience to delete for a specific audience only.

    Examples:
        faff timesheet rm today
        faff timesheet rm yesterday --audience element
        faff timesheet rm 2025-01-15
    """
    ws: Workspace = ctx.obj
    resolved_date = ws.parse_natural_date(date)

    if audience_id:
        # Delete for specific audience
        try:
            ws.timesheets.delete_timesheet(audience_id, resolved_date)
            typer.echo(f"Deleted timesheet for {audience_id} on {resolved_date}")
        except Exception as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)
    else:
        # Delete for all audiences
        audiences = ws.timesheets.audiences()
        deleted_count = 0
        errors = []

        for audience in audiences:
            try:
                ws.timesheets.delete_timesheet(audience.id, resolved_date)
                deleted_count += 1
                typer.echo(f"Deleted timesheet for {audience.id} on {resolved_date}")
            except Exception as e:
                # Only log error if it's not a "does not exist" error
                if "does not exist" not in str(e):
                    errors.append(f"{audience.id}: {e}")

        if deleted_count == 0:
            typer.echo(f"No timesheets found for {resolved_date}", err=True)
            raise typer.Exit(1)
        elif errors:
            typer.echo(f"Deleted {deleted_count} timesheet(s), but encountered errors:", err=True)
            for error in errors:
                typer.echo(f"  - {error}", err=True)
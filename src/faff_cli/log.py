import typer

from typing import List, Optional

from faff_cli import query

from faff_core import Workspace
from faff_core.models import Intent

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

app.add_typer(query.app, name="query")

@app.command()
def show(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    cli: faff log
    Show the log for today.
    """
    try:
        ws = ctx.obj
        resolved_date = ws.parse_natural_date(date)

        log = ws.logs.get_log_or_create(resolved_date)
        typer.echo(log.to_log_file(ws.plans.get_trackers(log.date)))
    except Exception as e:
        typer.echo(f"Error showing log: {e}", err=True)
        raise typer.Exit(1)

@app.command(name="list") # To avoid conflict with list type
def log_list(ctx: typer.Context):
    ws: Workspace = ctx.obj

    typer.echo("Private logs recorded for the following dates:")
    for log in ws.logs.list():
        # FIXME: It would be nicer if this included the start and end time of the day
        typer.echo(
            f"- {log.date} {log.date.strftime('%a').upper()} "
            f"{humanize.precisedelta(log.total_recorded_time(), minimum_unit='minutes')}"
            f"{' *UNCLOSED*' if not log.is_closed() else ''}"
        )

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
            log = ws.logs.get_log_or_create(resolved_date)
            trackers = ws.plans.get_trackers(resolved_date)
            ws.logs.write_log(log, trackers)

        if edit_file(Path(ws.logs.log_file_path(resolved_date))):
            typer.echo("Log file updated.")

            # Process the edited file again after editing
            if not skip_validation:
                log = ws.logs.get_log_or_create(resolved_date)
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

    log = ws.logs.get_log_or_create(resolved_date)

    trackers = ws.plans.get_trackers(log.date)

    # Loop through the logs, total all the time allocated to each tracker and for each tracker source, and print a summary.
    intent_tracker: Dict[Intent, datetime.timedelta] = {}
    tracker_totals: Dict[str, datetime.timedelta] = {}
    tracker_source_totals: Dict[str, datetime.timedelta] = {}

    for session in log.timeline:
        # Calculate the duration of the session
        if session.end is None:
            end_time = datetime.datetime.now(tz=log.timezone)
        else:
            end_time = session.end
        duration = end_time - session.start

        if session.intent not in intent_tracker:
            intent_tracker[session.intent] = datetime.timedelta()

        intent_tracker[session.intent] += duration

        for tracker in session.intent.trackers:
            if tracker not in tracker_totals:
                tracker_totals[tracker] = datetime.timedelta()

            tracker_source = tracker.split(":")[0] if ":" in tracker else ""
            if tracker_source not in tracker_source_totals:
                tracker_source_totals[tracker_source] = datetime.timedelta()

            tracker_totals[tracker] += duration
            tracker_source_totals[tracker_source] += duration

    # Format the summary
    summary = f"Summary for {resolved_date.isoformat()}:\n"
    summary += f"\nTotal recorded time: {humanize.precisedelta(log.total_recorded_time(),minimum_unit='minutes')}\n"
    summary += "\nIntent Totals:\n"
    for intent, total in intent_tracker.items():
        summary += f"- {intent.alias}: {humanize.precisedelta(total,minimum_unit='minutes')}\n"
    summary += "\nTracker Totals:\n"
    for tracker, total in tracker_totals.items():
        summary += f"- {tracker} - {trackers.get(tracker)}: {humanize.precisedelta(total,minimum_unit='minutes')}\n"
    summary += "\nTracker Source Totals:\n"
    for source, total in tracker_source_totals.items():
        summary += f"- {source}: {humanize.precisedelta(total,minimum_unit='minutes')}\n"

    typer.echo(summary)

@app.command()
def refresh(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    cli: faff log refresh
    Reformat the log file.
    """
    ws = ctx.obj

    # Sanitize date input
    if date:
        date = ws.parse_date(date)
    else:
        date = ws.today()

    log = ws.logs.get_log_or_create(date)
    trackers = ws.plans.get_trackers(date)
    ws.logs.write_log(log, trackers)
    typer.echo("Log refreshed.")
import typer

from typing import List, Optional

from faff_cli import query

from faff_core import Workspace
from faff_core.models import Intent

from faff_cli.private_log_formatter import PrivateLogFormatter
from faff_cli.utils import edit_file
from faff_cli.file_utils import FileSystemUtils

from faff_cli.utils import resolve_natural_date

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
    ws = ctx.obj
    resolved_date = resolve_natural_date(ws.today(), date)

    log = ws.logs.get_log(resolved_date)
    typer.echo(PrivateLogFormatter.format_log(log, ws.plans.get_trackers(log.date)))

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
def rm(ctx: typer.Context, date: str):
    """
    cli: faff log rm
    Remove the log for today.
    """
    # ws = ctx.obj

    # resolved_date = resolve_natural_date(ws.today(), date)

    # TODO: Implement the remove functionality

    #if ws.logs.rm(resolved_date):
    #    typer.echo(f"Log for {resolved_date} removed.")
    #else:
    #    typer.echo(f"No log found for {resolved_date}.")

@app.command()
def edit(ctx: typer.Context,
         date: str = typer.Argument(None),
         skip_validation: bool = typer.Option(False, "--force")):
    """
    cli: faff log edit
    Edit the log for the specified date, defaulting to today, in your default editor.
    """
    ws = ctx.obj

    resolved_date = resolve_natural_date(ws.today(), date)

    # Process the log to ensure it's correctly formatted for reading
    if not skip_validation:
        log = ws.logs.get_log(resolved_date)
        trackers = ws.plans.get_trackers(resolved_date)
        ws.logs.write_log(log, trackers)

    if edit_file(FileSystemUtils.get_log_path(resolved_date)):
        typer.echo("Log file updated.")

        # Process the edited file again after editing
        if not skip_validation:
            log = ws.logs.get_log(resolved_date)
            trackers = ws.plans.get_trackers(resolved_date)
            ws.logs.write_log(log, trackers)
    else:
        typer.echo("No changes detected.")


@app.command()
def summary(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    cli: faff log summary
    Show a summary of the log for today.
    """
    ws: Workspace = ctx.obj
    resolved_date: datetime.date = resolve_natural_date(ws.today(), date)

    log = ws.logs.get_log(resolved_date)

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

    log = ws.logs.get_log(date)
    trackers = ws.plans.get_trackers(date)
    ws.logs.write_log(log, trackers)
    typer.echo("Log refreshed.")
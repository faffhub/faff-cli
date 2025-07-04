import typer

from faff.core import PrivateLogFormatter, Workspace
from faff_core.models import Intent

from faff_cli.utils import edit_file

from faff_cli.utils import resolve_natural_date

from typing import Dict
import pendulum

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
    ws = ctx.obj
    resolved_date = resolve_natural_date(ws.today(), date)

    log = ws.logs.get_log(resolved_date)
    typer.echo(PrivateLogFormatter.format_log(log, ws.plans.get_trackers(log.date)))

@app.command(name="list") # To avoid conflict with list type
def log_list(ctx: typer.Context):
    ws = ctx.obj

    typer.echo("Private logs recorded for the following dates:")
    for log in ws.logs.list():
        # FIXME: It would be nicer if this included the start and end time of the day
        typer.echo(f"- {log.date} {log.date.format('ddd').upper()} {log.total_recorded_time().in_words()}{' *UNCLOSED*' if not log.is_closed() else ''}")

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
        ws.logs.write_log(ws.logs.get_log(resolved_date))

    if edit_file(ws.fs.log_path(resolved_date)):
        typer.echo("Log file updated.")

        # Process the edited file again after editing
        if not skip_validation:
            ws.logs.write_log(ws.logs.get_log(resolved_date))
    else:
        typer.echo("No changes detected.")


@app.command()
def summary(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    cli: faff log summary
    Show a summary of the log for today.
    """
    ws: Workspace = ctx.obj
    resolved_date = resolve_natural_date(ws.today(), date)

    log = ws.logs.get_log(resolved_date)

    trackers = ws.plans.get_trackers(log.date)

    # Loop through the logs, total all the time allocated to each tracker and for each tracker source, and print a summary.
    intent_tracker: Dict[Intent, pendulum.Duration] = {}
    tracker_totals: Dict[str, pendulum.Duration] = {}
    tracker_source_totals: Dict[str, pendulum.Duration] = {}

    for session in log.timeline:
        # Calculate the duration of the session
        if session.end is None:
            end_time = pendulum.now(str(log.timezone))
        else:
            end_time = session.end
        duration = end_time - session.start

        if session.intent not in intent_tracker:
            intent_tracker[session.intent] = pendulum.duration(0)

        intent_tracker[session.intent] += duration

        for tracker in session.intent.trackers:
            if tracker not in tracker_totals:
                tracker_totals[tracker] = pendulum.duration(0)

            tracker_source = tracker.split(":")[0] if ":" in tracker else ""
            if tracker_source not in tracker_source_totals:
                tracker_source_totals[tracker_source] = pendulum.duration(0)

            tracker_totals[tracker] += duration
            tracker_source_totals[tracker_source] += duration

    # Format the summary
    summary = f"Summary for {resolved_date.format('YYYY-MM-DD')}:\n"
    summary += f"\nTotal recorded time: {log.total_recorded_time().in_words()}\n"
    summary += "\nIntent Totals:\n"
    for intent, total in intent_tracker.items():
        summary += f"- {intent.alias}: {total.in_words()}\n"
    summary += "\nTracker Totals:\n"
    for tracker, total in tracker_totals.items():
        summary += f"- {tracker} - {trackers.get(tracker)}: {total.in_words()}\n"
    summary += "\nTracker Source Totals:\n"
    for source, total in tracker_source_totals.items():
        summary += f"- {source}: {total.in_words()}\n"  

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

    ws.logs.write_log(ws.logs.get_log(date))
    typer.echo("Log refreshed.")
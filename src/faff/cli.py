import subprocess
import pendulum
import typer
import os

from pathlib import Path

from faff.core import Workspace
from faff.core import LogFormatter
from faff.core import PullPlugin, PushPlugin, CompilePlugin

cli = typer.Typer()

cli_log = typer.Typer(help="Edit or append to the log")
cli_plan = typer.Typer(help="View plan(s)")
cli_source = typer.Typer(help="View and pull plans from source(s)")
cli_report = typer.Typer(help="Generate, sign, and push reports(s)")

cli.add_typer(cli_log, name="log")
cli.add_typer(cli_plan, name="plan")
cli.add_typer(cli_source, name="source")
cli.add_typer(cli_report, name="report")

"""
Design considerations:
- These methods should not expect _text_ to be returned from the context methods.
- Expected usage:
    faff init
    faff status
    faff source list
    faff source pull
    faff plan list
    faff log
    faff log edit
    faff log edit <date>
    faff log start <UUID> "Notes"
    faff log stop
    faff report list
    faff report compile <audience>
    faff report sign <id>
    faff report push <id>
"""

def edit_file(path: Path):
    editor = os.getenv("EDITOR", "vim")  # Default to vim if $EDITOR is not set

    pre_edit_hash = path.read_text().__hash__()
    # Open the file in the editor
    try:
        subprocess.run([editor, str(path)], check=True)
    except FileNotFoundError:
        return

    post_edit_hash = path.read_text().__hash__()

    # FIXME: This would be better if we returned None on successful change and
    # raised an error on no changes detected.
    if pre_edit_hash == post_edit_hash:
        typer.echo("No changes detected.")
    else:
        typer.echo("File updated.")

@cli.callback()
def main(ctx: typer.Context):
    ctx.obj = Workspace()

@cli.command()
def init(ctx: typer.Context):
    """
    Initialise faff obj.
    """
    ws = ctx.obj

    typer.echo("Initialising faff repository.")
    ws.fs.initialise_repo()
    faff_root = ws.fs.require_faff_root()
    typer.echo(f"Initialised faff repository at {faff_root}.")

@cli.command()
def config(ctx: typer.Context):
    """
    Edit the faff configuration in your preferred editor.
    """
    ws = ctx.obj
    edit_file(ws.fs.CONFIG_PATH)

@cli.command()
def status(ctx: typer.Context):
    """
    Show the status of the faff repository.
    """
    ws = ctx.obj
    typer.echo(f"Status for faff repo root at: {ws.fs.find_faff_root()}")

    todays_plans = ws.get_plans(ws.today())
    if len(todays_plans) == 1:
        typer.echo(f"There is 1 valid plan for today:")
    else:
        typer.echo(f"There are {len(todays_plans)} valid plans for today:")

    for plan in todays_plans:
        typer.echo(f"- {plan.source} (valid from {plan.valid_from})")

    # FIXME: don't use this private method
    plugins = ws._load_plugins()
    if len(plugins) == 1:
        typer.echo(f"There is 1 connector plugin installed:")
    else:
        typer.echo(f"There are {len(plugins)} connector plugins installed:")

    for plugin_name, plugin in plugins.items():
        types = []
        if issubclass(plugin, PullPlugin):
            types.append("pull")
        if issubclass(plugin, PushPlugin):
            types.append("push")
        if issubclass(plugin, CompilePlugin):
            types.append("compile")
        typer.echo(f"- {plugin_name} ({', '.join(types)})")

    log = ws.get_log(ws.today())

    total_recorded_time = pendulum.duration(0)
    for entry in log.timeline:
        if entry.end is None:
            duration = ws.now() - entry.start
        else:
            duration = entry.end - entry.start

        total_recorded_time += duration

    typer.echo(f"Total recorded time for today: {total_recorded_time.in_words()}")

    active_timeline_entry = log.active_timeline_entry()

    if active_timeline_entry:
        duration = ws.now() - active_timeline_entry.start
        if active_timeline_entry.note:
            typer.echo(f"Working on {active_timeline_entry.activity.name} (\"{active_timeline_entry.note}\") for {duration.in_words()}")
        else:
            typer.echo(f"Working on {active_timeline_entry.activity.name} for {duration.in_words()}")
    else:
        typer.echo("Not currently working on anything.")


def get_date(workspace: Workspace, date: str = None) -> pendulum.Date:
    """
    Get a date object from an argument string, or use the current date.
    """
    if date:
        return pendulum.parse(date).date()
    else:
        return workspace.today()

@cli_log.callback(invoke_without_command=True)
def log_callback(ctx: typer.Context):
    """
    Show the log for today.
    """
    if ctx.invoked_subcommand is None:
        ws = ctx.obj
        log = ws.get_log(ws.today())
        if log:
            typer.echo(LogFormatter.format_log(log, ws.get_activities(log.date)))
        else:
            typer.echo("No log found for today.")


@cli_log.command()
def edit(ctx: typer.Context, date: str = typer.Argument(None)):
    """Log your activities for the day by opening a file in your preferred editor."""
    ws = ctx.obj
    ws.write_log(ws.get_log(get_date(ws, date)))
    edit_file(ws.fs.log_path(get_date(ws, date)))
    ws.write_log(ws.get_log(get_date(ws, date)))


@cli_log.command()
def start(ctx: typer.Context, activity_id: str, note: str = typer.Argument(None)):
    """
    Add an entry to today's Private Log, starting now.
    """
    ws = ctx.obj
    typer.echo(ws.start_timeline_entry(activity_id, note))

@cli_log.command()
def stop(ctx: typer.Context):
    """
    Stop the current timeline entry.
    """
    ws = ctx.obj
    typer.echo(ws.stop_timeline_entry())

@cli_log.command()
def refresh(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    Reformat the log file.
    """
    ws = ctx.obj
    ws.write_log(ws.get_log(get_date(ws, date)))
    typer.echo("Log refreshed.")

@cli_plan.command(name="list") # To avoid conflict with list type
def list_plans(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    Show the planned activities for a given day, defaulting to today
    """
    ws = ctx.obj

    plans = ws.get_plans(get_date(ws, date))
    for plan in plans:
        typer.echo(f"Plan: {plan.source} (valid from {plan.valid_from})")
        for activity in plan.activities:
            typer.echo(f"- {activity.id}: {activity.name}")

@cli_source.command(name="list") # To avoid conflict with list type
def list_sources(ctx: typer.Context):
    """
    Show the available sources.
    """
    ws = ctx.obj
    plugins = ws.plan_sources()
    if len(plugins) == 1:
        typer.echo(f"There is 1 plan source configured:")
    else:
        typer.echo(f"There are {len(plugins)} plan sources configured:")
    for plugin_name, plugin in plugins.items():
        typer.echo(f"- {plugin_name} ({plugin.__class__.__name__})")

@cli_source.command()
def pull(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    Pull planned activities from all sources.
    """
    ws = ctx.obj
    plugins = ws.plan_sources()
    for plugin in plugins.values():
        ws.write_plan(plugin, ws.today())

if __name__ == "__main__":
    cli()
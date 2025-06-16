import typer

from faff_cli import log, id, source, plan, compiler, start
from faff_cli.utils import edit_file

from faff.core import Workspace

cli = typer.Typer()

cli.add_typer(log.app, name="log")
cli.add_typer(source.app, name="source")
cli.add_typer(compiler.app, name="compiler")
cli.add_typer(id.app, name="id")
cli.add_typer(plan.app, name="plan")
cli.add_typer(start.app, name="start")

"""
faff init                         # initialise faff repository        ✅
faff plan                         # show today's intents             ✅
faff stop                         # stop current task                 ✅
faff status                       # show working state                ✅
faff log                          # show today's log                  ✅
faff log edit                     # edit today's log                  ✅
faff log refresh                  # reformat today's log              ✅
faff pull                         # fetch latest plans                ✅
faff compile                      # compile today's work
faff push                         # submit timesheet
faff config edit                  # edit faff config                  ✅
"""

@cli.callback()
def main(ctx: typer.Context):
    ctx.obj = Workspace()

@cli.command()
def init(ctx: typer.Context):
    """
    cli: faff init
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
    cli: faff config
    Edit the faff configuration in your preferred editor.
    """
    ws = ctx.obj
    if edit_file(ws.fs.CONFIG_PATH):
        typer.echo("Configuration file was updated.")
    else:
        typer.echo("No changes detected.")

@cli.command()
def compile(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    cli: faff compile
    Compile the timesheet for a given date, defaulting to today.
    """
    ws = ctx.obj
    plugins = ws.compilers()
    for plugin in plugins.values():
        ws.timesheets.write_timesheet(plugin, ws.today())

@cli.command()
def status(ctx: typer.Context):
    """
    cli: faff status
    Show the status of the faff repository.
    """
    ws = ctx.obj
    typer.echo(f"Status for faff repo root at: {ws.fs.find_faff_root()}")

    log = ws.logs.get_log(ws.today())
    typer.echo(f"Total recorded time for today: {log.total_recorded_time().in_words()}")

    active_timeline_entry = log.active_timeline_entry()
    if active_timeline_entry:
        duration = ws.now() - active_timeline_entry.start
        if active_timeline_entry.note:
            typer.echo(f"Working on {active_timeline_entry.alias} (\"{active_timeline_entry.note}\") for {duration.in_words()}")
        else:
            typer.echo(f"Working on {active_timeline_entry.alias} for {duration.in_words()}")
    else:
        typer.echo("Not currently working on anything.")

@cli.command()
def stop(ctx: typer.Context):
    """
    Stop the current timeline entry.
    """
    ws = ctx.obj
    typer.echo(ws.logs.stop_current_timeline_entry())

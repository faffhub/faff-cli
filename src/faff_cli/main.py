import typer

from faff_cli import log, id, source, plan, compiler, start, timesheet
from faff_cli.utils import edit_file

from faff.core import Workspace

cli = typer.Typer()

cli.add_typer(log.app, name="log")
cli.add_typer(source.app, name="source")
cli.add_typer(compiler.app, name="compiler")
cli.add_typer(id.app, name="id")
cli.add_typer(plan.app, name="plan")
cli.add_typer(start.app, name="start")
cli.add_typer(timesheet.app, name="timesheet")

@cli.callback()
def main(ctx: typer.Context):
    ctx.obj = Workspace()

@cli.command()
def init(ctx: typer.Context):
    """
    cli: faff init
    Initialise faff obj.
    """
    ws: Workspace = ctx.obj

    typer.echo("Initialising faff repository.")
    ws.fs.initialise_repo()
    faff_root = ws.fs.find_faff_root()
    if faff_root:
        typer.echo(f"Initialised faff repository at {faff_root}.")
    else:
        typer.echo("Failed to initialise faff repository. Please check your permissions and try again.")
        exit(1)

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

    active_session = log.active_session()
    if active_session:
        duration = ws.now() - active_session.start
        if active_session.note:
            typer.echo(f"Working on {active_session.alias} (\"{active_session.note}\") for {duration.in_words()}")
        else:
            typer.echo(f"Working on {active_session.alias} for {duration.in_words()}")
    else:
        typer.echo("Not currently working on anything.")

@cli.command()
def stop(ctx: typer.Context):
    """
    Stop the current timeline entry.
    """
    ws: Workspace = ctx.obj
    typer.echo(ws.logs.stop_current_session())

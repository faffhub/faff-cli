import typer
import humanize

from faff_cli import log, id, plan, compiler, start, timesheet, intent, field, remote
from faff_cli.utils import edit_file

import faff_core
from faff_core import Workspace, FileSystemStorage

from pathlib import Path

cli = typer.Typer()

cli.add_typer(log.app, name="log")
cli.add_typer(compiler.app, name="compiler")
cli.add_typer(id.app, name="id")
cli.add_typer(plan.app, name="plan")
cli.add_typer(start.app, name="start")
cli.add_typer(timesheet.app, name="timesheet")
cli.add_typer(intent.app, name="intent")
cli.add_typer(field.app, name="field")
cli.add_typer(remote.app, name="remote")

@cli.callback()
def main(ctx: typer.Context):
    # Don't create workspace for init command - it doesn't need one
    if ctx.invoked_subcommand == "init":
        ctx.obj = None
    else:
        ctx.obj = Workspace()

@cli.command()
def init(ctx: typer.Context,
         target_dir_str: str,
         force: bool = typer.Option(False, "--force", help="Allow init inside a parent faff repo")):
    """
    cli: faff init
    Initialise faff obj.
    """
    # init doesn't need a workspace - ctx.obj will be None
    target_dir = Path(target_dir_str)
    if not target_dir.exists():
        typer.echo(f"Target directory {target_dir} does not exist.")
        exit(1)

    typer.echo("Initialising faff repository.")
    try:
        storage = FileSystemStorage.init_at(str(target_dir), force)
        typer.echo(f"Initialised faff repository at {storage.root_dir()}.")
    except Exception as e:
        typer.echo(f"Failed to initialise faff repository: {e}")
        exit(1)

@cli.command()
def config(ctx: typer.Context):
    """
    cli: faff config
    Edit the faff configuration in your preferred editor.
    """
    ws = ctx.obj
    from pathlib import Path
    if edit_file(Path(ws.storage().config_file())):
        typer.echo("Configuration file was updated.")
    else:
        typer.echo("No changes detected.")

@cli.command()
def compile(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    cli: faff compile
    Compile the timesheet for a given date, defaulting to today.
    """
    try:
        ws = ctx.obj
        resolved_date = ws.parse_natural_date(date)

        log = ws.logs.get_log_or_create(resolved_date)
        audiences = ws.timesheets.audiences()

        for audience in audiences:
            compiled_timesheet = audience.compile_time_sheet(log)
            ws.timesheets.write_timesheet(compiled_timesheet)
            typer.echo(f"Compiled timesheet for {resolved_date} using {audience.id}.")
    except Exception as e:
        typer.echo(f"Error compiling timesheet: {e}", err=True)
        raise typer.Exit(1)

@cli.command()
def status(ctx: typer.Context):
    """
    cli: faff status
    Show the status of the faff repository.
    """
    try:
        ws: Workspace = ctx.obj
        typer.echo(f"Status for faff repo root at: {ws.storage().root_dir()}")
        typer.echo(f"faff-core library version: {faff_core.version()}")

        log = ws.logs.get_log_or_create(ws.today())
        typer.echo(f"Total recorded time for today: {humanize.precisedelta(log.total_recorded_time(),minimum_unit='minutes')}")

        active_session = log.active_session()
        if active_session:
            duration = ws.now() - active_session.start
            if active_session.note:
                typer.echo(f"Working on {active_session.intent.alias} (\"{active_session.note}\") for {humanize.precisedelta(duration)}")
            else:
                typer.echo(f"Working on {active_session.intent.alias} for {humanize.precisedelta(duration)}")
        else:
            typer.echo("Not currently working on anything.")
    except Exception as e:
        typer.echo(f"Error getting status: {e}", err=True)
        raise typer.Exit(1)

@cli.command()
def stop(ctx: typer.Context):
    """
    Stop the current timeline entry.
    """
    try:
        ws: Workspace = ctx.obj
        typer.echo(ws.logs.stop_current_session())
    except Exception as e:
        typer.echo(f"Error stopping session: {e}", err=True)
        raise typer.Exit(1)

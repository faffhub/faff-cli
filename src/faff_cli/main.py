import typer
import humanize

from faff_cli import log, id, source, plan, compiler, start, timesheet
from faff_cli.utils import edit_file
from faff_cli.file_utils import FileSystemUtils

import faff_core
from faff_core import Workspace

from pathlib import Path

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
def init(ctx: typer.Context,
         target_dir_str: str,
         force: bool = typer.Option(False, "--force", help="Allow init inside a parent faff repo")):
    """
    cli: faff init
    Initialise faff obj.
    """
    ws: Workspace = ctx.obj

    target_dir = Path(target_dir_str)
    if not target_dir.exists():
        typer.echo(f"Target directory {target_dir} does not exist.")
        exit(1)

    typer.echo("Initialising faff repository.")
    FileSystemUtils.initialise_repo(target_dir, force)
    faff_root = FileSystemUtils.find_faff_root(target_dir)
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
    if edit_file(FileSystemUtils.get_config_path()):
        typer.echo("Configuration file was updated.")
    else:
        typer.echo("No changes detected.")

@cli.command()
def compile(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    cli: faff compile
    Compile the timesheet for a given date, defaulting to today.
    """
    from faff_cli.utils import resolve_natural_date

    ws = ctx.obj
    resolved_date = resolve_natural_date(ws.today(), date)

    log = ws.logs.get_log_or_create(resolved_date)
    audiences = ws.timesheets.audiences()

    for audience in audiences:
        compiled_timesheet = audience.compile_time_sheet(log)
        ws.timesheets.write_timesheet(compiled_timesheet)
        typer.echo(f"Compiled timesheet for {resolved_date} using {audience.id}.")

@cli.command()
def rust(ctx: typer.Context):

    ws: Workspace = ctx.obj

    import faff_core
    print(faff_core.hello_world())

    from faff_core.models import Toy

    t = Toy("Hello from Rust via an object!")
    # print(t.do_a_datetime(ws.now()))
    import datetime
    import zoneinfo
    print(repr(t.add_days(datetime.datetime.now(zoneinfo.ZoneInfo("Europe/London")), 5)))


@cli.command()
def status(ctx: typer.Context):
    """
    cli: faff status
    Show the status of the faff repository.
    """
    ws: Workspace = ctx.obj
    typer.echo(f"Status for faff repo root at: {FileSystemUtils.get_faff_root()}")
    typer.echo(f"faff-core library version: {faff_core.version()}")

    log = ws.logs.get_log_or_create(ws.today())
    typer.echo(f"Total recorded time for today: {humanize.precisedelta(log.total_recorded_time(),minimum_unit='minutes')}")

    active_session = log.active_session()
    if active_session:
        typer.echo(f"Currently working on {active_session.intent.alias}.")
        duration = ws.now() - active_session.start
        if active_session.note:
            typer.echo(f"Working on {active_session.intent.alias} (\"{active_session.note}\") for {humanize.precisedelta(duration)}")
        else:
            typer.echo(f"Working on {active_session.intent.alias} for {humanize.precisedelta(duration)}")
    else:
        typer.echo("Not currently working on anything.")

@cli.command()
def stop(ctx: typer.Context):
    """
    Stop the current timeline entry.
    """
    ws: Workspace = ctx.obj
    typer.echo(ws.logs.stop_current_session())

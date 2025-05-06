import typer

from InquirerPy import inquirer

from faff_cli import log, connection, id
from faff_cli.utils import edit_file

from faff.core import Workspace

cli = typer.Typer()

cli.add_typer(log.app, name="log")
cli.add_typer(connection.app, name="connection")
cli.add_typer(id.app, name="id")

"""
faff init                         # initialise faff repository        ✅
faff plan                         # show today's activities           ✅
faff start <activity-id> [note]   # start work                        ✅
faff stop                         # stop current task                 ✅
faff status                       # show working state                ✅
faff log                          # show today's log                  ✅
faff log edit                     # edit today's log                  ✅
faff log refresh                  # reformat today's log              ✅
faff pull                         # fetch latest plans                ✅
faff compile                      # compile today's work
faff push                         # submit timesheet
faff config edit                  # edit faff config                  ✅
faff connection list              # see configured connections        ✅
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
            typer.echo(f"Working on {active_timeline_entry.activity.name} (\"{active_timeline_entry.note}\") for {duration.in_words()}")
        else:
            typer.echo(f"Working on {active_timeline_entry.activity.name} for {duration.in_words()}")
    else:
        typer.echo("Not currently working on anything.")

@cli.command()
def start(
    ctx: typer.Context,
    activity_id: str = typer.Argument(None),
    note: str = typer.Argument(None),
):
    """
    Add an entry to today's Private Log, starting now.
    """
    ws = ctx.obj
    date = ws.today()

    if activity_id is None:
        activities = ws.plans.get_activities(date)

        if not activities:
            typer.echo("No valid activities for today.")
            raise typer.Exit(1)

        choices = [
            {"name": f"{a.name} ({ws.plans.get_plan_by_activity_id(a.id, date).source})", "value": a.id}
            for a in activities.values()
        ]

        # FIXME: We should show the source plan, too.
        activity_id = inquirer.fuzzy(
            message="Select an activity to start:",
            choices=choices,
        ).execute()

        if note is None:
            note = inquirer.text(message="Optional note:").execute()

    typer.echo(ws.logs.start_timeline_entry_now(activity_id, note))

@cli.command()
def stop(ctx: typer.Context):
    """
    Stop the current timeline entry.
    """
    ws = ctx.obj
    typer.echo(ws.logs.stop_current_timeline_entry())

@cli.command()
def plan(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    Show the planned activities for a given day, defaulting to today
    """
    ws = ctx.obj

    if date:
        date = ws.parse_date(date)
    else:
        date = ws.today()

    plans = ws.plans.get_plans(date).values()
    for plan in plans:
        typer.echo(f"Plan: {plan.source} (valid from {plan.valid_from})")
        for activity in plan.activities:
            typer.echo(f"- {activity.id}: {activity.name}")

@cli.command()
def pull(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    cli: faff pull
    Pull planned activities from all sources.
    """
    ws = ctx.obj
    sources = ws.plans.sources()
    for source in sources:
        ws.plans.write_plan(source, ws.today())
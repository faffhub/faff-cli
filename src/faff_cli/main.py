import typer

from InquirerPy import inquirer

from faff_cli import log, connection, id, source, plan, compiler
from faff_cli.utils import edit_file
from faff_cli.ui import fuzzy_select

from faff.core import Workspace
from faff_cli.utils import resolve_natural_date

from faff.models import Intent

cli = typer.Typer()

cli.add_typer(log.app, name="log")
cli.add_typer(source.app, name="source")
cli.add_typer(connection.app, name="connection")
cli.add_typer(compiler.app, name="compiler")
cli.add_typer(id.app, name="id")
cli.add_typer(plan.app, name="plan")

"""
faff init                         # initialise faff repository        ✅
faff plan                         # show today's buckets           ✅
faff start <bucket-id> [note]   # start work                        ✅
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
            typer.echo(f"Working on {active_timeline_entry.name} (\"{active_timeline_entry.note}\") for {duration.in_words()}")
        else:
            typer.echo(f"Working on {active_timeline_entry.name} for {duration.in_words()}")
    else:
        typer.echo("Not currently working on anything.")


@cli.command()
def start(ctx: typer.Context):

    ws = ctx.obj
    date = ws.today()

    intents = ws.plans.get_intents(date)
    x = []
    for intent in intents:
        x.append({
            "name": intent.get_alias(),
            "value": intent
        })

    intent, new = fuzzy_select(prompt="I am doing:", choices=x, escapable=True)
    if not intent:
        # No intent found, so we need to create a new one.
        activity, new = fuzzy_select("I am doing:", ws.plans.get_activities(date))
        role, new = fuzzy_select("as:", ws.plans.get_roles(date))
        goal, new = fuzzy_select("to achieve:", ws.plans.get_goals(date))
        beneficiary, new = fuzzy_select("for:", ws.plans.get_beneficiaries(date))

        buckets = ws.plans.get_buckets(ws.today())

        choices = [
            {"name": f"{a.name} ({ws.plans.get_plan_by_bucket_id(a.id, date).source})", "value": a.id}
            for a in buckets.values()
        ]
        bucket_id, _ = fuzzy_select(
            prompt="Tracked under (esc for none):",
            choices=choices,
            create_new=False,
            escapable=True
        )

        if bucket_id:
            bucket_id = bucket_id.get("value", None)

        suggested_name = f"{role}: {activity[0].upper() + activity[1:]} to {goal} for {beneficiary}"
        alias, _ = fuzzy_select(
            prompt="Name (esc for none):",
            choices=[suggested_name],
            create_new=True,
            escapable=True
        )


        local_plan = ws.plans.local_plan(date)
        new_plan = local_plan.add_intent(Intent(
            alias=alias,
            role=role,
            activity=activity,
            goal=goal,
            beneficiary=beneficiary,
            bucket=bucket_id
        ))
        ws.plans.write_plan(new_plan)


    else:
        intent = intent.get("value", None)
        # We have an existing intent, so we can use that.
        activity = intent.activity
        role = intent.role
        goal = intent.goal
        beneficiary = intent.beneficiary
        alias = intent.alias
        bucket_id = intent.bucket

    typer.echo(ws.logs.start_intent_now(role, bucket_id, goal, beneficiary, alias, None, None))


@cli.command()
def ostart(
    ctx: typer.Context,
    bucket_id: str = typer.Argument(None),
    note: str = typer.Argument(None),
):
    """
    Add an entry to today's Private Log, starting now.
    """
    ws = ctx.obj
    date = ws.today()

    if bucket_id is None:
        buckets = ws.plans.get_buckets(date)

        if not buckets:
            typer.echo("No valid buckets for today.")
            raise typer.Exit(1)

        choices = [
            {"name": f"{a.name} ({ws.plans.get_plan_by_bucket_id(a.id, date).source})", "value": a.id}
            for a in buckets.values()
        ]

        # FIXME: We should show the source plan, too.
        bucket_id = inquirer.fuzzy(
            message="Select an bucket to start:",
            choices=choices,
        ).execute()

        if note is None:
            note = inquirer.text(message="Optional note:").execute()

    typer.echo(ws.logs.start_timeline_entry_now(bucket_id, note))

@cli.command()
def stop(ctx: typer.Context):
    """
    Stop the current timeline entry.
    """
    ws = ctx.obj
    typer.echo(ws.logs.stop_current_timeline_entry())



@cli.command()
def pull(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    cli: faff pull
    Pull planned buckets from all sources.
    """
    ws = ctx.obj

    resolved_date = resolve_natural_date(ws.today(), date)

    sources = ws.plans.sources()
    for source in sources:
        plan = source.pull_plan(resolved_date)
        ws.plans.write_plan(plan)
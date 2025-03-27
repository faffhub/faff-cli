import typer
from faff import core
from faff.context import Context

cli = typer.Typer()

cli_log = typer.Typer(help="Edit or append to the log")
cli_plan = typer.Typer(help="Configure, pull, and view plan(s)")
cli_report = typer.Typer(help="Generate, sign, and push reports(s)")

cli.add_typer(cli_log, name="log")
cli.add_typer(cli_plan, name="plan")
cli.add_typer(cli_report, name="report")

"""
Design considerations:
- These methods should not expect _text_ to be returned from the context methods.
- Expected usage:
    faff init
    faff status
    faff plan add remote
    faff plan pull
    faff plan list
    faff log edit
    faff log edit <date>
    faff log start <UUID> "Notes"
    faff log stop
    faff report list
    faff report compile <audience>
    faff report sign <id>
    faff report push <id>
"""

@cli.callback()
def main(ctx: typer.Context):
    ctx.obj = Context()

@cli.command()
def init(ctx: typer.Context):
    """
    Initialise faff obj.
    """
    context = ctx.obj

    typer.echo("Initialising faff repository.")
    context.initialise_repo()
    faff_root = context.require_faff_root()
    typer.echo(f"Initialised faff repository at {faff_root}.")

@cli.command()
def status(ctx: typer.Context):
    """
    Show the status of the faff repository.
    """
    context = ctx.obj
    typer.echo(f"Faff root: {context.find_faff_root()}")

    todays_plans = core.load_valid_plans_for_day(context.find_faff_root(), core.today())
    typer.echo(f"There are {len(todays_plans)} valid plans for today:")
    for plan in todays_plans:
        typer.echo(f"- {plan.source} (valid from {plan.valid_from})")

@cli_log.command()
def edit(ctx: typer.Context):
    """Log your activities for the day by opening a file in your preferred editor."""
    context = ctx.obj

    todays_plans = core.load_valid_plans_for_day(context.find_faff_root(), core.today())
    
    core.log_end_of_day_editor(context.require_faff_root(),
                               todays_plans,
                               core.today(),
                               typer.echo)    


@cli_log.command()
def start(ctx: typer.Context, activity_id: str, note: str = typer.Argument(None)):
    """
    Add an entry to the day's Private Log.
    """
    context = ctx.obj
    valid_plans = core.load_valid_plans_for_day(context.require_faff_root(),
                                               core.today())
    typer.echo(core.start_timeline_entry(context.require_faff_root(),
                                         activity_id,
                                         note,
                                         valid_plans))

@cli_log.command()
def stop(ctx: typer.Context):
    """
    Stop the current timeline entry.
    """
    context = ctx.obj
    typer.echo(core.stop_timeline_entry(context.require_faff_root()))

@cli_plan.command()
def list(ctx: typer.Context):
    """
    Show the planned activities for today
    """
    context = ctx.obj
    todays_plans = core.load_valid_plans_for_day(context.find_faff_root(), core.today())
    for plan in todays_plans:
        typer.echo(f"Plan: {plan.source} (valid from {plan.valid_from})")
        for activity in plan.activities:
            typer.echo(f"- {activity.id}: {activity.name}")


if __name__ == "__main__":
    cli()
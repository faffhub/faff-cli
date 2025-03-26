import typer
from faff import core
from faff.context import Context

app = typer.Typer()

@app.command()
def status():
    """
    Show the status of the faff repository.
    """
    context = Context()
    typer.echo(f"Working directory: {context.working_dir}")
    typer.echo(f"Root directory: {context.find_faff_root()}")

    todays_plans = core.load_valid_plans_for_day(context.find_faff_root(), core.today())
    typer.echo(f"There are {len(todays_plans)} valid plans for today.")
    for plan in todays_plans:
        typer.echo(f"- {plan.source} (valid from {plan.valid_from})")


@app.command()
def init():
    """
    Initialise faff repository.
    """
    context = Context()

    typer.echo("Initialising faff repository.")
    context.initialise_repo()
    faff_root = context.require_faff_root()
    typer.echo(f"Initialised faff repository at {faff_root}.")


log_app = typer.Typer(help="Log stuff")
app.add_typer(log_app, name="log")


@log_app.command()
def new():
    """
    Initialise the day's Private Log.
    """
    typer.echo("Initialising the day's Private Log.")


@log_app.command()
def edit():
    """Log your activities for the day by opening a file in your preferred editor."""
    context = Context()

    todays_plans = core.load_valid_plans_for_day(context.find_faff_root(), core.today())
    
    core.log_end_of_day_editor(context.require_faff_root(),
                               todays_plans,
                               core.today(),
                               typer.echo)    


@log_app.command()
def start(activity_id: str, note: str = typer.Argument(None)):
    """
    Add an entry to the day's Private Log.
    """
    typer.echo("Add an entry to the day's Log.")
    valid_plans = core.load_valid_plans_for_day(Context().require_faff_root(),
                                               core.today())
    typer.echo(core.start_timeline_entry(Context().require_faff_root(),
                                         activity_id,
                                         note,
                                         valid_plans))


@log_app.command()
def stop():
    """
    Stop the current timeline entry.
    """
    typer.echo(core.stop_timeline_entry(Context().require_faff_root()))


plan_app = typer.Typer(help="Plan stuff")
app.add_typer(plan_app, name="plan")


@plan_app.command()
def show():
    """
    Show the planned activities for today
    """
    context = Context()
    todays_plans = core.load_valid_plans_for_day(context.find_faff_root(), core.today())
    for plan in todays_plans:
        typer.echo(f"Plan: {plan.source} (valid from {plan.valid_from})")
        for activity in plan.activities:
            typer.echo(f"- {activity.id}: {activity.name}")

if __name__ == "__main__":
    app()

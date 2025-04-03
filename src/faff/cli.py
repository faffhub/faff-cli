import typer
import pendulum
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
def config(ctx: typer.Context):
    """
    Edit the faff configuration in your preferred editor.
    """
    context = ctx.obj
    typer.echo(core.edit_config(context))

@cli.command()
def status(ctx: typer.Context):
    """
    Show the status of the faff repository.
    """
    context = ctx.obj
    typer.echo(f"Status for faff repo root at: {context.find_faff_root()}")

    todays_plans = core.load_valid_plans_for_day(context, context.today())
    if len(todays_plans) == 1:
        typer.echo(f"There is 1 valid plan for today:")
    else:
        typer.echo(f"There are {len(todays_plans)} valid plans for today:")

    for plan in todays_plans:
        typer.echo(f"- {plan.source} (valid from {plan.valid_from})")

    plugins = core.load_plugins(context)
    if len(plugins) == 1:
        typer.echo(f"There is 1 connector plugin installed:")
    else:
        typer.echo(f"There are {len(plugins)} connector plugins installed:")

    for plugin_name, plugin in plugins.items():
        types = []
        if issubclass(plugin, core.PullConnector):
            types.append("pull")
        if issubclass(plugin, core.PushConnector):
            types.append("push")
        typer.echo(f"- {plugin_name} ({', '.join(types)})")

    log = core.get_log_by_date(context, context.today())
    active_timeline_entry = log.active_timeline_entry()

    if active_timeline_entry:
        duration = context.now() - active_timeline_entry.start
        if active_timeline_entry.note:
            typer.echo(f"Working on {active_timeline_entry.activity.name} (\"{active_timeline_entry.note}\") for {duration.in_words()}")
        else:
            typer.echo(f"Working on {active_timeline_entry.activity.name} for {duration.in_words()}")
    else:
        typer.echo("Not currently working on anything.")


def get_date(context: Context, date: str = None) -> pendulum.Date:
    """
    Get a date object from an argument string, or use the current date.
    """
    if date:
        return pendulum.parse(date).date()
    else:
        return context.today()


@cli_log.command()
def edit(ctx: typer.Context, date: str = typer.Argument(None)):
    """Log your activities for the day by opening a file in your preferred editor."""
    context = ctx.obj
    typer.echo(core.edit_log(context, get_date(context, date)))


@cli_log.command()
def start(ctx: typer.Context, activity_id: str, note: str = typer.Argument(None)):
    """
    Add an entry to today's Private Log, starting now.
    """
    context = ctx.obj
    typer.echo(core.start_timeline_entry(context,
                                         activity_id,
                                         note))

@cli_log.command()
def stop(ctx: typer.Context):
    """
    Stop the current timeline entry.
    """
    context = ctx.obj
    typer.echo(core.stop_timeline_entry(context))

@cli_log.command()
def refresh(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    Reformat the log file.
    """
    context = ctx.obj
    log = core.get_log_by_date(context, get_date(context, date))
    core.write_log(context, log)
    typer.echo("Log refreshed.")

@cli_plan.command(name="list") # To avoid conflict with list type
def list_plans(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    Show the planned activities for a given day, defaulting to today
    """
    context = ctx.obj

    plans = core.load_valid_plans_for_day(context, get_date(context, date))
    for plan in plans:
        typer.echo(f"Plan: {plan.source} (valid from {plan.valid_from})")
        for activity in plan.activities:
            typer.echo(f"- {activity.id}: {activity.name}")


@cli_plan.command()
def pull(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    Pull planned activities from all sources.
    """
    context = ctx.obj
    plugins = core.load_plugins(context)
    jira = plugins.get('jira')().pull_plan(
        get_date(context, date),
        get_date(context, date), {})

    # write the plan to the plan folder:
    import toml
    import dataclasses

    def serialize_value(value):
        if isinstance(value, (pendulum.DateTime, pendulum.Date)):
            return value.to_date_string()  # or .to_iso8601_string() if datetime
        elif isinstance(value, dict):
            return {k: serialize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [serialize_value(v) for v in value]
        else:
            return value

    def serialize_dataclass(obj):
        return {k: serialize_value(v) for k, v in dataclasses.asdict(obj).items()}

    data = serialize_dataclass(jira)

    path = context.require_faff_root() / ".faff" / "plans" / f"remote.{jira.source}.{jira.valid_from.format('YYYYMMDD')}.toml"
    with path.open("w") as f:
        toml.dump(data, f)    

    typer.echo(f"Pulled plan from {jira.source} and saved to {path}")


if __name__ == "__main__":
    cli()
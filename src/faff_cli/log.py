import typer
import pendulum

from faff.core import PrivateLogFormatter

from faff_cli.utils import edit_file

app = typer.Typer(help="View, edit, and interact with private logs.")

"""
faff log
faff log edit
faff log refresh
"""

def resolve_natural_date(today: pendulum.Date, arg: str | None) -> pendulum.Date:
    if arg is None or arg.lower() == "today":
        return today
    if arg.lower() == "yesterday":
        return today.subtract(days=1)
    
    weekdays = {
        "monday": pendulum.MONDAY,
        "tuesday": pendulum.TUESDAY,
        "wednesday": pendulum.WEDNESDAY,
        "thursday": pendulum.THURSDAY,
        "friday": pendulum.FRIDAY,
        "saturday": pendulum.SATURDAY,
        "sunday": pendulum.SUNDAY,
    }

    weekday = weekdays.get(arg.lower())
    if weekday is not None:
        return today.previous(weekday)
    
    try:
        return pendulum.parse(arg).date()
    except Exception:
        raise typer.BadParameter(f"Unrecognized date: '{arg}'")

@app.command()
def show(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    cli: faff log
    Show the log for today.
    """
    ws = ctx.obj
    resolved_date = resolve_natural_date(ws.today(), date)

    log = ws.logs.get_log(resolved_date)
    typer.echo(PrivateLogFormatter.format_log(log, ws.plans.get_activities(log.date)))

@app.command(name="list") # To avoid conflict with list type
def log_list(ctx: typer.Context):
    ws = ctx.obj

    for log_file in ws.logs.list():
        typer.echo(log_file)

@app.command()
def edit(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    cli: faff log edit
    Log your activities for the day by opening a file in your preferred editor.
    """
    ws = ctx.obj

    resolved_date = resolve_natural_date(ws.today(), date)

    # Process the log to ensure it's correctly formatted for reading
    ws.logs.write_log(ws.logs.get_log(resolved_date))

    if edit_file(ws.fs.log_path(resolved_date)):
        typer.echo("Log file updated.")

        # Process the edited file again after editing
        ws.logs.write_log(ws.logs.get_log(resolved_date))
    else:
        typer.echo("No changes detected.")


@app.command()
def refresh(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    cli: faff log refresh
    Reformat the log file.
    """
    ws = ctx.obj

    # Sanitize date input
    if date:
        date = ws.parse_date(date)
    else:
        date = ws.today()

    ws.logs.write_log(ws.logs.get_log(date))
    typer.echo("Log refreshed.")
import typer

from faff.core import PrivateLogFormatter

from faff_cli.utils import edit_file

from faff_cli.utils import resolve_natural_date

app = typer.Typer(help="View, edit, and interact with private logs.")

"""
faff log
faff log edit
faff log refresh
"""

@app.command()
def show(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    cli: faff log
    Show the log for today.
    """
    ws = ctx.obj
    resolved_date = resolve_natural_date(ws.today(), date)

    log = ws.logs.get_log(resolved_date)
    typer.echo(PrivateLogFormatter.format_log(log, ws.plans.get_trackers(log.date)))

@app.command(name="list") # To avoid conflict with list type
def log_list(ctx: typer.Context):
    ws = ctx.obj

    typer.echo("Private logs recorded for the following dates:")
    for log in ws.logs.list():
        # FIXME: It would be nicer if this included the start and end time of the day
        typer.echo(f"- {log.date} {log.total_recorded_time().in_words()}{' *UNCLOSED*' if not log.is_closed() else ''}")

@app.command()
def rm(ctx: typer.Context, date: str):
    """
    cli: faff log rm
    Remove the log for today.
    """
    # ws = ctx.obj

    # resolved_date = resolve_natural_date(ws.today(), date)

    # TODO: Implement the remove functionality

    #if ws.logs.rm(resolved_date):
    #    typer.echo(f"Log for {resolved_date} removed.")
    #else:
    #    typer.echo(f"No log found for {resolved_date}.")

@app.command()
def edit(ctx: typer.Context,
         date: str = typer.Argument(None),
         force: bool = typer.Option(False, "--force")):
    """
    cli: faff log edit
    Edit the log for the specified date, defaulting to today, in your default editor.
    """
    ws = ctx.obj

    resolved_date = resolve_natural_date(ws.today(), date)

    # Process the log to ensure it's correctly formatted for reading
    if not force:
        ws.logs.write_log(ws.logs.get_log(resolved_date))

    if edit_file(ws.fs.log_path(resolved_date)):
        typer.echo("Log file updated.")

        # Process the edited file again after editing
        if not force:
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
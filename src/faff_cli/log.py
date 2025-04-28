import typer

from faff.core import LogFormatter

from faff_cli.utils import edit_file

app = typer.Typer(help="View, edit, and interact with private logs.")

"""
faff log
faff log edit
faff log refresh
"""

@app.callback(invoke_without_command=True)
def log(ctx: typer.Context):
    """
    cli: faff log
    Show the log for today.
    """
    if ctx.invoked_subcommand is None:
        ws = ctx.obj
        log = ws.get_log(ws.today())
        if log:
            typer.echo(LogFormatter.format_log(log, ws.get_activities(log.date)))
        else:
            typer.echo("No log found for today.")

@app.command()
def edit(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    cli: faff log edit
    Log your activities for the day by opening a file in your preferred editor.
    """
    ws = ctx.obj

    # Sanitize date input
    if date:
        date = ws.parse_date(date)
    else:
        date = ws.today()

    # Process the log to ensure it's correctly formatted for reading
    ws.write_log(ws.get_log(date))

    if edit_file(ws.fs.log_path(date)):
        typer.echo("Log file updated.")

        # Process the edited file again after editing
        ws.write_log(ws.get_log(date))
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

    ws.write_log(ws.get_log(date))
    typer.echo("Log refreshed.")
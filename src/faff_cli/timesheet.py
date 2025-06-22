import typer

from faff_cli.utils import resolve_natural_date
from faff.core import Workspace


app = typer.Typer(help="Do Timesheet stuffs.")

@app.command()
def audiences(ctx: typer.Context):
    """
    List the configured audiences.
    """
    ws: Workspace = ctx.obj

    compilers = ws.timesheets.audiences()
    typer.echo(f"Found {len(compilers)} configured timesheet compiler(s):")
    for compiler in compilers:
        typer.echo(f"- {compiler.id} {compiler.__class__.__name__}")
    
@app.command()
def compile(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    Compile the timesheet for a given date, defaulting to today.
    """
    ws: Workspace = ctx.obj
    resolved_date = resolve_natural_date(ws.today(), date)
    
    log = ws.logs.get_log(resolved_date)

    compilers = ws.timesheets.audiences()
    for compiler in compilers:
        compiled_timesheet = compiler.compile_time_sheet(log)
        key = ws.identities.get_identity("tom@element.io")
        if key:
            signed_sheet = compiled_timesheet.sign("tom@element.io", key)
            ws.timesheets.write_timesheet(signed_sheet)
            typer.echo(f"Compiled and signed timesheet for {resolved_date} using {compiler.id}.")
        else:
            typer.echo("No identity key found for signing timesheet. Skipping signing.")
            ws.timesheets.write_timesheet(compiled_timesheet)

@app.command(name="list") # To avoid conflict with list type
def list_timesheets(ctx: typer.Context):
    ws: Workspace = ctx.obj

    typer.echo("Timesheets generated:")
    for timesheet in ws.timesheets.list():
        line = f"- {timesheet.meta.audience_id} {timesheet.date} (generated at {timesheet.compiled}"
        if timesheet.meta.submitted_at:
            line += f"; submitted at {timesheet.meta.submitted_at}"
        if timesheet.meta.submitted_by:
            line += f" by {timesheet.meta.submitted_by}"
        else:
            line += "; not submitted"
        line += ")"
        typer.echo(line)

@app.command()
def show(ctx: typer.Context, audience_id: str, date: str = typer.Argument(None)):
    ws: Workspace = ctx.obj
    resolved_date = resolve_natural_date(ws.today(), date)

    timesheet = ws.timesheets.get_timesheet(audience_id, resolved_date)
    import json
    if timesheet:
        data = json.loads(timesheet.submittable_timesheet().canonical_form().decode("utf-8"))
        typer.echo(json.dumps(data, indent=2))



@app.command()
def submit(ctx: typer.Context, audience_id: str, date: str = typer.Argument(None)):
    """
    Push the timesheet for a given date, defaulting to today.
    """
    ws: Workspace = ctx.obj
    resolved_date = resolve_natural_date(ws.today(), date)

    timesheet = ws.timesheets.get_timesheet(audience_id, resolved_date)
    if timesheet:
        ws.timesheets.submit(timesheet)
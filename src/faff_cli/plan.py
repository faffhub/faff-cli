import typer

from faff_cli.utils import edit_file

app = typer.Typer(help="View, edit, and interact with downloaded plans.")

"""
faff log
faff log edit
faff log refresh
"""

from faff_cli.utils import resolve_natural_date

@app.command(name="list")
def list_plans(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    Show the planned activities for a given day, defaulting to today
    """
    ws = ctx.obj
    resolved_date = resolve_natural_date(ws.today(), date)

    plans = ws.plans.get_plans(resolved_date).values()
    typer.echo(f"Found {len(plans)} plan(s) active on {resolved_date}:")
    for plan in plans:
        typer.echo(f"- {plan.source} {plan.valid_from}{' ' + plan.valid_until if plan.valid_until else '..'}")

def list_plans(ctx: typer.Context, date: str = typer.Argument(None)):
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
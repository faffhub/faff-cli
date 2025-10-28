import typer

from faff_core import Workspace

app = typer.Typer(help="View, edit, and interact with downloaded plans.")

"""
faff log
faff log edit
faff log refresh
"""

@app.command(name="list")
def list_plans(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    Show the planned activities for a given day, defaulting to today
    """
    ws: Workspace = ctx.obj
    resolved_date = ws.parse_natural_date(date)

    plans = ws.plans.get_plans(resolved_date).values()
    typer.echo(f"Found {len(plans)} plan(s) active on {resolved_date}:")
    for plan in plans:
        typer.echo(f"- {plan.source} {plan.valid_from}{' ' + str(plan.valid_until) if plan.valid_until else '..'}")

@app.command()
def remotes(ctx: typer.Context):
    """
    Show the available plan remotes.
    """
    ws: Workspace = ctx.obj
    remotes = ws.plans.remotes()
    typer.echo(f"Found {len(remotes)} configured plan remote(s):")
    for remote in remotes:
        typer.echo(f"- {remote.id} {remote.__class__.__name__}")

@app.command()
def show(ctx: typer.Context,
         #plan_id: str = typer.Argument(None),
         date: str = typer.Argument(None)):
    """
    Show the planned activities for a given day, defaulting to today
    """
    ws: Workspace = ctx.obj
    resolved_date = ws.parse_natural_date(date)

    plans = ws.plans.get_plans(resolved_date).values()
    for plan in plans:
        typer.echo(f"Plan: {plan.source} (valid from {plan.valid_from})")
        print(plan.to_toml())

@app.command()
def pull(ctx: typer.Context, remote_id: str = typer.Argument(None)):
    """
    Pull the plans from a given source.
    """
    ws: Workspace = ctx.obj
    remotes = ws.plans.remotes()

    if remote_id:
        remotes = [r for r in remotes if r.id == remote_id]
        if len(remotes) == 0:
            raise typer.BadParameter(f"Unknown source: {remote_id}")

    for remote in remotes:
        plan = remote.pull_plan(ws.today())
        if plan:
            ws.plans.write_plan(plan)
            typer.echo(f"Pulled plans from {remote.name}")
        else:
            typer.echo(f"No plans found for {remote.name}")
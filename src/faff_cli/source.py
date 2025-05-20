import typer

app = typer.Typer(help="View, edit, and interact with plan sources.")

@app.command(name="list")
def list_sources(ctx: typer.Context):
    """
    Show the available sources.
    """
    ws = ctx.obj
    sources = ws.plans.sources()
    typer.echo(f"Found {len(sources)} configured source(s):")
    for source in sources:
        typer.echo(f"- {source.id} {source.__class__.__name__}")

@app.command()
def pull(ctx: typer.Context, source_id: str):
    """
    Pull the plans from a given source.
    """
    ws = ctx.obj
    sources = ws.plans.sources()
    source = [s for s in sources if s.id == source_id][0]
    if source is None:
        raise typer.BadParameter(f"Unknown source: {source_id}")

    plan = source.pull_plan(ws.today())
    if plan:
        ws.plans.write_plan(plan)
        typer.echo(f"Pulled plans from {source.name}")
    else:
        typer.echo(f"No plans found for {source.name}")
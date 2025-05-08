import typer

app = typer.Typer(help="View, edit, and interact with plan sources.")

@app.command(name="list")
def list_sources(ctx: typer.Context):
    """
    Show the available sources.
    """
    ws = ctx.obj
    sources = ws.plans.sources()
    if len(sources) == 1:
        typer.echo(f"There is 1 plan source configured:")
    else:
        typer.echo(f"There are {len(sources)} plan sources configured:")
    for source in sources:
        typer.echo(f"- {source.name} ({source.__class__.__name__})")

@app.command()
def pull(ctx: typer.Context, name: str):
    """
    Pull the plans from a given source.
    """
    ws = ctx.obj
    sources = ws.plans.sources()
    source = [s for s in sources if s.name == name][0]
    if source is None:
        raise typer.BadParameter(f"Unknown source: {name}")

        ws.plans.write_plan(source, ws.today())   
    ws.plans.write_plan(source, ws.today())
    typer.echo(f"Pulled plans from {source.name}")
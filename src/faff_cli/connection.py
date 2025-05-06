import typer

from faff.plugins import PullPlugin, PushPlugin, CompilePlugin

app = typer.Typer(help="View connections")

"""
faff connection status
faff connection list
"""

@app.command()
def status(ctx: typer.Context):
    """
    cli: faff connection status
    """
    ws = ctx.obj
    # FIXME: don't use this private method
    plugins = ws.plugins.load_plugins()
    if len(plugins) == 1:
        typer.echo(f"There is 1 connector plugin installed:")
    else:
        typer.echo(f"There are {len(plugins)} connector plugins installed:")

    for plugin_name, plugin in plugins.items():
        types = []
        if issubclass(plugin, PullPlugin):
            types.append("pull")
        if issubclass(plugin, PushPlugin):
            types.append("push")
        if issubclass(plugin, CompilePlugin):
            types.append("compile")
        typer.echo(f"- {plugin_name} ({', '.join(types)})")

@app.command(name="list") # To avoid conflict with list type
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
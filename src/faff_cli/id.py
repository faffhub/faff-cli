import typer

app = typer.Typer(help="View, edit, and interact with private logs.")

"""
faff id list
"""

@app.command(name="list") # To avoid conflict with list type
def list_ids(ctx: typer.Context):
    """
    Show the available sources.
    """
    ws = ctx.obj
    ids = ws.identities.get()
    if len(ids) == 1:
        typer.echo("There is 1 ID configured:")
    else:
        typer.echo(f"There are {len(ids)} IDs configured:")
    for id in ids.keys():
        typer.echo(f"- {id}")

@app.command()
def create(ctx: typer.Context, name: str, overwrite: bool = False):
    """
    Create a new identity key pair.
    """
    ws = ctx.obj
    key = ws.identities.create_identity(name, overwrite)
    typer.echo(f"Created identity '{name}' with public key {key.verify_key.encode()}")
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
    ids = [1,2,3]
    typer.echo(f"There are {len(ids)} IDs configured:")

@app.command()
def create(ctx: typer.Context, name: str, overwrite: bool = False):
    """
    Create a new identity key pair.
    """
    ws = ctx.obj
    key = ws.identities.create_identity(name, overwrite)
    typer.echo(f"Created identity '{name}' with public key {key.verify_key.encode()}")
import typer
import base64

from faff_core import Workspace

app = typer.Typer(help="View, edit, and interact with identities.")

"""
faff id list
"""

@app.command(name="list") # To avoid conflict with list type
def list_ids(ctx: typer.Context):
    """
    Show the available ids.
    """
    ws: Workspace = ctx.obj
    ids = ws.identities.get()
    typer.echo(f"Found {len(ids)} ID(s) configured:")
    for id in ids.keys():
        typer.echo(f"- {id}")

@app.command()
def create(ctx: typer.Context, name: str, overwrite: bool = False):
    """
    Create a new identity key pair.
    """
    ws = ctx.obj
    key = ws.identities.create_identity(name, overwrite)
    typer.echo(f"Created identity '{name}' with public key {base64.b64encode(key.verify_key.encode()).decode()}")
import typer

app = typer.Typer(help="View, edit, and interact with timesheet compilers.")

@app.command(name="list") # To avoid conflict with list type
def log_list(ctx: typer.Context):
    ws = ctx.obj

    compilers = ws.compilers.get()
    typer.echo(f"Found {len(compilers)} configured timesheet compiler(s):")
    for compiler in compilers:
        typer.echo(f"- {compiler.id} {compiler.__class__.__name__}")

import typer
from pathlib import Path

from rich.console import Console
from rich.table import Table

from faff_core import Workspace

app = typer.Typer(help="Manage remote plugin instances")


@app.command(name="list")
def list_remotes(ctx: typer.Context):
    """
    List all configured remotes.
    """
    try:
        ws: Workspace = ctx.obj
        console = Console()

        remotes_dir = Path(ws.storage().remotes_dir())
        remote_files = list(remotes_dir.glob("*.toml"))

        if not remote_files:
            console.print("[yellow]No remotes configured[/yellow]")
            console.print(f"\nRemotes are configured in: {remotes_dir}")
            console.print("Create a .toml file there to configure a remote.")
            return

        table = Table(title="Configured Remotes")
        table.add_column("ID", style="cyan")
        table.add_column("Plugin", style="green")
        table.add_column("Config File", style="dim")

        import toml

        for remote_file in sorted(remote_files):
            try:
                remote_data = toml.load(remote_file)
                remote_id = remote_data.get("id", remote_file.stem)
                plugin = remote_data.get("plugin", "unknown")
                table.add_row(remote_id, plugin, remote_file.name)
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Failed to read {remote_file.name}: {e}[/yellow]"
                )

        console.print(table)
        console.print(f"\nRemotes directory: {remotes_dir}")

    except Exception as e:
        typer.echo(f"Error listing remotes: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def show(ctx: typer.Context, remote_id: str = typer.Argument(..., help="Remote ID to show")):
    """
    Show detailed configuration for a remote.
    """
    try:
        ws: Workspace = ctx.obj
        console = Console()

        remotes_dir = Path(ws.storage().remotes_dir())
        remote_file = remotes_dir / f"{remote_id}.toml"

        if not remote_file.exists():
            console.print(f"[red]Remote '{remote_id}' not found[/red]")
            console.print(f"\nLooking for: {remote_file}")
            raise typer.Exit(1)

        import toml

        remote_data = toml.load(remote_file)

        console.print(f"[bold cyan]Remote: {remote_id}[/bold cyan]\n")
        console.print(f"[bold]Plugin:[/bold] {remote_data.get('plugin', 'unknown')}")
        console.print(f"[bold]Config file:[/bold] {remote_file}\n")

        # Show connection config
        if "connection" in remote_data and remote_data["connection"]:
            console.print("[bold]Connection:[/bold]")
            for key, value in remote_data["connection"].items():
                # Hide sensitive values
                if "key" in key.lower() or "token" in key.lower() or "password" in key.lower():
                    console.print(f"  {key}: [dim]<hidden>[/dim]")
                else:
                    console.print(f"  {key}: {value}")
            console.print()

        # Show vocabulary
        if "vocabulary" in remote_data and remote_data["vocabulary"]:
            console.print("[bold]Vocabulary:[/bold]")
            vocab = remote_data["vocabulary"]
            for field_name in ["roles", "objectives", "actions", "subjects"]:
                if field_name in vocab and vocab[field_name]:
                    console.print(f"  {field_name}: {len(vocab[field_name])} items")
                    for item in vocab[field_name]:
                        console.print(f"    - {item}")
        else:
            console.print("[dim]No vocabulary configured[/dim]")

    except Exception as e:
        typer.echo(f"Error showing remote: {e}", err=True)
        raise typer.Exit(1)

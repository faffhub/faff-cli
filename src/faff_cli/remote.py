import typer
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.table import Table

from faff_core import Workspace
from faff_cli.output import create_formatter
from faff_cli.filtering import parse_simple_filters, apply_filters

app = typer.Typer(help="Manage remote plugin instances")


@app.command(name="list")
def list_remotes(
    ctx: typer.Context,
    filter_strings: List[str] = typer.Argument(
        None,
        help="Filters: field=value (exact), field~value (contains), field!=value (not equal)",
    ),
    limit: Optional[int] = typer.Option(
        None,
        "--limit", "-n",
        help="Limit number of results",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    plain_output: bool = typer.Option(
        False,
        "--plain",
        help="Output as plain text (no colors)",
    ),
):
    """
    List all configured remotes with optional filtering.

    Supports filtering by ID and plugin name.
    Shows remote ID, plugin type, and configuration file.

    Examples:
        faff remote list
        faff remote list id=element
        faff remote list plugin~jira
        faff remote list --json
    """
    try:
        ws: Workspace = ctx.obj

        # Parse filters using Python-side parsing
        filters = []
        if filter_strings:
            try:
                filters = parse_simple_filters(filter_strings)
            except ValueError as e:
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(1)

        remotes_dir = Path(ws.storage().remotes_dir())
        remote_files = list(remotes_dir.glob("*.toml"))

        # Build remote data list
        remote_data = []
        import toml

        for remote_file in sorted(remote_files):
            try:
                data = toml.load(remote_file)
                remote_id = data.get("id", remote_file.stem)
                plugin = data.get("plugin", "unknown")

                remote_data.append({
                    "id": remote_id,
                    "plugin": plugin,
                    "config_file": remote_file.name,
                })
            except Exception as e:
                # In non-JSON mode, show warnings
                if not json_output:
                    typer.echo(f"Warning: Failed to read {remote_file.name}: {e}", err=True)

        # Apply filters
        if filters:
            remote_data = apply_filters(remote_data, filters)

        # Sort by ID (alphabetically)
        remote_data.sort(key=lambda x: x["id"])

        # Apply limit
        if limit:
            remote_data = remote_data[:limit]

        # Create output formatter
        formatter = create_formatter(json_output, plain_output)

        # Define columns for table output
        columns = [
            ("id", "ID", "cyan"),
            ("plugin", "Plugin", "green"),
            ("config_file", "Config File", "dim"),
        ]

        # Output results
        formatter.print_table(
            remote_data,
            columns,
            title="Configured Remotes",
            total_label="remotes" if remote_data else None,
        )

        if not remote_data:
            if not json_output:
                formatter.print_message("No remotes found matching criteria.", "yellow")
                formatter.print_message(f"\nRemotes are configured in: {remotes_dir}", "")
                formatter.print_message("Create a .toml file there to configure a remote.", "")
        else:
            if not json_output:
                typer.echo(f"\nRemotes directory: {remotes_dir}")

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error listing remotes: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


@app.command()
def add(
    ctx: typer.Context,
    remote_id: str = typer.Argument(..., help="ID for the remote"),
    plugin: str = typer.Argument(..., help="Plugin name (e.g., 'my-hours', 'jira')"),
):
    """
    Create a new remote configuration.

    If the plugin has a config.template.toml, it will be used as the base.
    Otherwise, a minimal configuration will be created.
    """
    try:
        ws: Workspace = ctx.obj
        console = Console()

        remotes_dir = Path(ws.storage().remotes_dir())
        remote_file = remotes_dir / f"{remote_id}.toml"

        if remote_file.exists():
            console.print(f"[red]Remote '{remote_id}' already exists[/red]")
            console.print(f"File: {remote_file}")
            console.print("\nUse 'faff remote edit' to modify it.")
            raise typer.Exit(1)

        # Check if plugin exists and has a template
        plugins_dir = Path(ws.storage().base_dir()) / "plugins"
        plugin_dir = plugins_dir / plugin
        template_path = plugin_dir / "config.template.toml"

        if template_path.exists():
            # Use the plugin's template
            template_content = template_path.read_text()
            config = template_content.replace("{{instance_name}}", remote_id)
            console.print(f"[green]Created remote '{remote_id}' from plugin template[/green]")
        else:
            # Create minimal remote config
            config = f"""id = "{remote_id}"
plugin = "{plugin}"

[connection]
# Add your connection details here

[vocabulary]
# Add static ROAST vocabulary items here (optional)
"""
            if plugin_dir.exists():
                console.print(f"[yellow]Note: Plugin '{plugin}' has no template[/yellow]")
            console.print(f"[green]Created remote '{remote_id}' with minimal config[/green]")

        remote_file.write_text(config)
        console.print(f"File: {remote_file}")
        console.print(f"\nRun: [cyan]faff remote edit {remote_id}[/cyan] to configure")

    except Exception as e:
        typer.echo(f"Error adding remote: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def edit(ctx: typer.Context, remote_id: str = typer.Argument(..., help="Remote ID to edit")):
    """
    Edit a remote configuration in your preferred editor.
    """
    try:
        ws: Workspace = ctx.obj
        console = Console()

        remotes_dir = Path(ws.storage().remotes_dir())
        remote_file = remotes_dir / f"{remote_id}.toml"

        if not remote_file.exists():
            console.print(f"[red]Remote '{remote_id}' not found[/red]")
            console.print(f"\nRun: [cyan]faff remote add {remote_id} <plugin>[/cyan]")
            raise typer.Exit(1)

        from faff_cli.utils import edit_file

        if edit_file(remote_file):
            console.print(f"[green]Remote '{remote_id}' updated[/green]")
        else:
            console.print("No changes detected.")

    except Exception as e:
        typer.echo(f"Error editing remote: {e}", err=True)
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

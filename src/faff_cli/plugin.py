"""Plugin management commands.

NOTE: This module intentionally violates the principle of "CLI should not interact directly
with files on disk". Plugin installation/management is a CLI concern, not a core library
concern. The Rust library only needs to know how to discover and run plugins, not install them.
"""

import subprocess
import shutil
from pathlib import Path
import typer
from faff_core import Workspace

app = typer.Typer(help="Manage plugins")


@app.command()
def install(
    ctx: typer.Context,
    github_url: str = typer.Argument(..., help="GitHub URL of the plugin to install")
):
    """
    Install a plugin from GitHub by cloning it into .faff/plugins/.

    Example:
        faff plugin install https://github.com/user/faff-plugin-myhours
    """
    ws: Workspace = ctx.obj

    # Extract repo name from URL
    # Handle both https://github.com/user/repo and git@github.com:user/repo.git
    if github_url.endswith('.git'):
        repo_name = github_url.split('/')[-1][:-4]
    else:
        repo_name = github_url.split('/')[-1]

    # Determine the plugins directory
    plugins_dir = Path(ws.storage().base_dir()) / "plugins"
    plugins_dir.mkdir(exist_ok=True)

    plugin_dir = plugins_dir / repo_name

    if plugin_dir.exists():
        typer.echo(f"Plugin '{repo_name}' is already installed at {plugin_dir}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Installing plugin '{repo_name}' from {github_url}...")

    try:
        # Clone the repository (shallow clone to minimize disk usage)
        subprocess.run(
            ["git", "clone", "--depth", "1", "--single-branch", github_url, str(plugin_dir)],
            check=True,
            capture_output=True,
            text=True
        )

        # Validate it's a proper plugin (has plugin/ directory)
        plugin_code_dir = plugin_dir / "plugin"
        if not plugin_code_dir.exists():
            typer.echo(f"Error: {repo_name} doesn't appear to be a valid faff plugin (missing 'plugin/' directory)", err=True)
            shutil.rmtree(plugin_dir)
            raise typer.Exit(1)

        typer.echo(f"✓ Successfully installed plugin '{repo_name}' to {plugin_dir}")

        # Check if there's a config template
        template_path = plugin_dir / "config.template.toml"
        if template_path.exists():
            typer.echo("\nTo create a remote using this plugin, run:")
            typer.echo(f"  faff remote add <remote-id> {repo_name}")
        else:
            typer.echo("\nWarning: No config.template.toml found. You'll need to create a config manually.")

    except subprocess.CalledProcessError as e:
        typer.echo(f"Error cloning repository: {e.stderr}", err=True)
        # Clean up partial installation
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)
        raise typer.Exit(1)


@app.command("list")
def list_plugins(ctx: typer.Context):
    """
    List all installed plugins and their instances.
    """
    ws: Workspace = ctx.obj

    plugins_dir = Path(ws.storage().base_dir()) / "plugins"

    if not plugins_dir.exists():
        typer.echo("No plugins directory found.")
        return

    # Get all plugin directories
    plugins = [p for p in plugins_dir.iterdir() if p.is_dir() and not p.name.startswith('.')]

    if not plugins:
        typer.echo("No plugins installed.")
        typer.echo("\nInstall a plugin with:")
        typer.echo("  faff plugin install <github-url>")
        return

    typer.echo("Installed plugins:")

    for plugin_dir in sorted(plugins):
        plugin_name = plugin_dir.name

        # Validate plugin structure
        has_template = (plugin_dir / "config.template.toml").exists()
        has_plugin_dir = (plugin_dir / "plugin").exists() and (plugin_dir / "plugin").is_dir()

        # Determine status indicator
        if has_template and has_plugin_dir:
            status = ""
        else:
            missing = []
            if not has_plugin_dir:
                missing.append("plugin/")
            if not has_template:
                missing.append("config.template.toml")
            status = f" [⚠ missing: {', '.join(missing)}]"

        typer.echo(f"\n  {plugin_name}{status}")
        typer.echo(f"    Location: {plugin_dir}")

        # Find instances (configs in remotes/ that use this plugin)
        remote_configs = ws.plugins.get_remote_configs()
        instances = [config["id"] for config in remote_configs if config["plugin"] == plugin_name]

        if instances:
            typer.echo(f"    Instances: {', '.join(sorted(instances))}")

@app.command()
def update(
    ctx: typer.Context,
    plugin_name: str = typer.Argument(..., help="Name of the plugin to update")
):
    """
    Update an installed plugin by pulling the latest changes from its GitHub repository.
    """
    ws: Workspace = ctx.obj

    plugins_dir = Path(ws.storage().base_dir()) / "plugins"
    plugin_dir = plugins_dir / plugin_name

    if not plugin_dir.exists():
        typer.echo(f"Plugin '{plugin_name}' is not installed.", err=True)
        raise typer.Exit(1)

    typer.echo(f"Updating plugin '{plugin_name}'...")

    try:
        # Pull the latest changes
        result = subprocess.run(
            ["git", "-C", str(plugin_dir), "pull"],
            check=True,
            capture_output=True,
            text=True
        )

        typer.echo(result.stdout)
        typer.echo(f"✓ Successfully updated plugin '{plugin_name}'")

    except subprocess.CalledProcessError as e:
        typer.echo(f"Error updating plugin: {e.stderr}", err=True)
        raise typer.Exit(1)

@app.command()
def uninstall(
    ctx: typer.Context,
    plugin_name: str = typer.Argument(..., help="Name of the plugin to uninstall")
):
    """
    Uninstall a plugin by removing it from .faff/plugins/.

    Note: This does not remove instance configs in .faff/remotes/
    """
    ws: Workspace = ctx.obj

    plugins_dir = Path(ws.storage().base_dir()) / "plugins"
    plugin_dir = plugins_dir / plugin_name

    if not plugin_dir.exists():
        typer.echo(f"Plugin '{plugin_name}' is not installed.", err=True)
        raise typer.Exit(1)

    # Check for instances
    remote_configs = ws.plugins.get_remote_configs()
    instances = [config["id"] for config in remote_configs if config["plugin"] == plugin_name]

    if instances:
        typer.echo("Warning: The following instances use this plugin:")
        for instance in instances:
            typer.echo(f"  - {instance}")

        confirm = typer.confirm("\nAre you sure you want to uninstall?")
        if not confirm:
            typer.echo("Uninstall cancelled.")
            raise typer.Exit(0)

    # Remove the plugin directory
    shutil.rmtree(plugin_dir)

    typer.echo(f"✓ Uninstalled plugin '{plugin_name}'")

    if instances:
        typer.echo("\nNote: Instance configs still exist in .faff/remotes/")
        typer.echo("You may want to remove them manually.")

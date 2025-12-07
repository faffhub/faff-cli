"""Plugin management commands.

NOTE: This module intentionally violates the principle of "CLI should not interact directly
with files on disk". Plugin installation/management is a CLI concern, not a core library
concern. The Rust library only needs to know how to discover and run plugins, not install them.
"""

import subprocess
import shutil
import sys
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

        # Check for and handle requirements.txt
        requirements_path = plugin_dir / "requirements.txt"
        if requirements_path.exists():
            typer.echo(f"\nFound requirements.txt. Setting up isolated environment...")

            # Create a venv for this plugin
            plugin_venv = plugin_dir / ".venv"
            try:
                typer.echo(f"  Creating virtual environment at {plugin_venv}...")
                subprocess.run(
                    [sys.executable, "-m", "venv", str(plugin_venv)],
                    check=True,
                    capture_output=True,
                    text=True
                )

                # Determine pip path in the new venv
                if sys.platform == "win32":
                    venv_pip = plugin_venv / "Scripts" / "pip"
                else:
                    venv_pip = plugin_venv / "bin" / "pip"

                # Install requirements into the plugin's venv
                typer.echo(f"  Installing dependencies...")
                subprocess.run(
                    [str(venv_pip), "install", "-r", str(requirements_path)],
                    check=True,
                    capture_output=True,
                    text=True
                )

                # Find the plugin venv's site-packages directory
                result = subprocess.run(
                    [str(venv_pip), "show", "-f", "pip"],
                    check=True,
                    capture_output=True,
                    text=True
                )
                # Parse the Location field from pip show output
                plugin_site_packages = None
                for line in result.stdout.split('\n'):
                    if line.startswith('Location:'):
                        plugin_site_packages = Path(line.split(':', 1)[1].strip())
                        break

                if not plugin_site_packages:
                    raise RuntimeError("Could not determine plugin venv site-packages directory")

                # Find the main venv's site-packages directory
                main_site_packages = Path(sys.executable).parent.parent / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
                if not main_site_packages.exists():
                    # Alternative location for some systems
                    main_site_packages = Path(sys.executable).parent.parent / "lib" / "site-packages"

                if not main_site_packages.exists():
                    raise RuntimeError(f"Could not find main venv site-packages directory at {main_site_packages}")

                # Create a .pth file in the main venv pointing to plugin's site-packages
                pth_file = main_site_packages / f"faff-plugin-{repo_name}.pth"
                pth_file.write_text(str(plugin_site_packages) + "\n")

                typer.echo(f"✓ Created isolated environment and installed dependencies")
                typer.echo(f"  Site-packages linked via: {pth_file.name}")

            except subprocess.CalledProcessError as e:
                typer.echo(f"Error setting up plugin environment: {e.stderr}", err=True)
                typer.echo(f"You may need to manually install dependencies.", err=True)
            except Exception as e:
                typer.echo(f"Error setting up plugin environment: {e}", err=True)
                typer.echo(f"You may need to manually install dependencies.", err=True)

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

        # Check if plugin needs venv setup (new or updated requirements.txt)
        requirements_path = plugin_dir / "requirements.txt"
        plugin_venv = plugin_dir / ".venv"

        if requirements_path.exists() and not plugin_venv.exists():
            typer.echo(f"\nFound requirements.txt. Setting up isolated environment...")

            try:
                # Create a venv for this plugin
                typer.echo(f"  Creating virtual environment at {plugin_venv}...")
                subprocess.run(
                    [sys.executable, "-m", "venv", str(plugin_venv)],
                    check=True,
                    capture_output=True,
                    text=True
                )

                # Determine pip path in the new venv
                if sys.platform == "win32":
                    venv_pip = plugin_venv / "Scripts" / "pip"
                else:
                    venv_pip = plugin_venv / "bin" / "pip"

                # Install requirements into the plugin's venv
                typer.echo(f"  Installing dependencies...")
                subprocess.run(
                    [str(venv_pip), "install", "-r", str(requirements_path)],
                    check=True,
                    capture_output=True,
                    text=True
                )

                # Find the plugin venv's site-packages directory
                result = subprocess.run(
                    [str(venv_pip), "show", "-f", "pip"],
                    check=True,
                    capture_output=True,
                    text=True
                )
                plugin_site_packages = None
                for line in result.stdout.split('\n'):
                    if line.startswith('Location:'):
                        plugin_site_packages = Path(line.split(':', 1)[1].strip())
                        break

                if not plugin_site_packages:
                    raise RuntimeError("Could not determine plugin venv site-packages directory")

                # Find the main venv's site-packages directory
                main_site_packages = Path(sys.executable).parent.parent / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
                if not main_site_packages.exists():
                    main_site_packages = Path(sys.executable).parent.parent / "lib" / "site-packages"

                if not main_site_packages.exists():
                    raise RuntimeError(f"Could not find main venv site-packages directory at {main_site_packages}")

                # Create a .pth file in the main venv pointing to plugin's site-packages
                pth_file = main_site_packages / f"faff-plugin-{plugin_name}.pth"
                pth_file.write_text(str(plugin_site_packages) + "\n")

                typer.echo(f"✓ Created isolated environment and installed dependencies")
                typer.echo(f"  Site-packages linked via: {pth_file.name}")

            except subprocess.CalledProcessError as e:
                typer.echo(f"Error setting up plugin environment: {e.stderr}", err=True)
            except Exception as e:
                typer.echo(f"Error setting up plugin environment: {e}", err=True)

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

    # Clean up .pth file if it exists
    main_site_packages = Path(sys.executable).parent.parent / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    if not main_site_packages.exists():
        main_site_packages = Path(sys.executable).parent.parent / "lib" / "site-packages"

    pth_file = main_site_packages / f"faff-plugin-{plugin_name}.pth"
    if pth_file.exists():
        pth_file.unlink()
        typer.echo(f"✓ Removed site-packages link: {pth_file.name}")

    typer.echo(f"✓ Uninstalled plugin '{plugin_name}'")

    if instances:
        typer.echo("\nNote: Instance configs still exist in .faff/remotes/")
        typer.echo("You may want to remove them manually.")

@app.command()
def doctor(ctx: typer.Context):
    """
    Check the health of all installed plugins.

    Diagnoses common issues like missing dependencies, broken venvs, or import errors.
    """
    ws: Workspace = ctx.obj
    from rich.console import Console
    console = Console()

    plugins_dir = Path(ws.storage().base_dir()) / "plugins"

    if not plugins_dir.exists():
        console.print("[yellow]No plugins directory found.[/yellow]")
        return

    # Get all plugin directories
    plugins = [p for p in plugins_dir.iterdir() if p.is_dir() and not p.name.startswith('.')]

    if not plugins:
        console.print("[yellow]No plugins installed.[/yellow]")
        return

    console.print("[bold]Plugin Health Check[/bold]\n")

    # Find main venv site-packages
    main_site_packages = Path(sys.executable).parent.parent / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    if not main_site_packages.exists():
        main_site_packages = Path(sys.executable).parent.parent / "lib" / "site-packages"

    for plugin_dir in sorted(plugins):
        plugin_name = plugin_dir.name
        console.print(f"[cyan]{plugin_name}[/cyan]")

        issues = []
        warnings = []

        # Check plugin structure
        has_plugin_dir = (plugin_dir / "plugin").exists() and (plugin_dir / "plugin").is_dir()
        has_plugin_py = (plugin_dir / "plugin" / "plugin.py").exists()
        has_requirements = (plugin_dir / "requirements.txt").exists()
        has_venv = (plugin_dir / ".venv").exists()

        if not has_plugin_dir:
            issues.append("Missing plugin/ directory")
        if not has_plugin_py:
            issues.append("Missing plugin/plugin.py")

        # Check dependency setup
        if has_requirements:
            if not has_venv:
                issues.append("Has requirements.txt but no .venv (run 'faff plugin update' to fix)")
            else:
                # Check .pth file
                pth_file = main_site_packages / f"faff-plugin-{plugin_name}.pth"
                if not pth_file.exists():
                    issues.append(f"Missing .pth file at {pth_file}")
                else:
                    # Verify .pth file points to correct location
                    pth_content = pth_file.read_text().strip()
                    expected_path = plugin_dir / ".venv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
                    if pth_content != str(expected_path):
                        warnings.append(f".pth file points to {pth_content} (may be outdated)")

        # Try to import the plugin module
        if has_plugin_py:
            try:
                # Try importing using importlib
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    plugin_name,
                    str(plugin_dir / "plugin" / "plugin.py")
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    console.print("  [green]✓[/green] Plugin imports successfully")
            except ModuleNotFoundError as e:
                issues.append(f"Import error: {e} (missing dependency?)")
            except Exception as e:
                issues.append(f"Import error: {e}")

        # Report findings
        if issues:
            for issue in issues:
                console.print(f"  [red]✗[/red] {issue}")
        elif warnings:
            for warning in warnings:
                console.print(f"  [yellow]⚠[/yellow] {warning}")
        else:
            if not has_requirements:
                console.print("  [green]✓[/green] Healthy (no dependencies)")
            else:
                console.print("  [green]✓[/green] Healthy")

        console.print()

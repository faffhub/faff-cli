import typer
from typing import Optional

from faff_core import Workspace
from faff_cli.output import create_formatter

app = typer.Typer(help="View, edit, and interact with downloaded plans.")


@app.command(name="list")
def list_plans(
    ctx: typer.Context,
    date: str = typer.Argument(None, help="Date to show plans for (defaults to today)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    plain_output: bool = typer.Option(False, "--plain", help="Output as plain text (no colors)"),
):
    """
    List all plans active on a given date.

    Shows plans from all sources (local and remote) that are valid on the specified date.

    Examples:
        faff plan list
        faff plan list yesterday
        faff plan list 2025-01-15
        faff plan list --json
    """
    try:
        ws: Workspace = ctx.obj
        resolved_date = ws.parse_natural_date(date)

        plans = list(ws.plans.get_plans(resolved_date).values())

        # Build plan data for output
        plan_data = []
        for plan in plans:
            valid_until_str = str(plan.valid_until) if plan.valid_until else "∞"
            intent_count = len(plan.intents)

            plan_data.append({
                "source": plan.source,
                "valid_from": str(plan.valid_from),
                "valid_until": valid_until_str,
                "intent_count": intent_count,
            })

        # Create formatter and output
        formatter = create_formatter(json_output, plain_output)
        columns = [
            ("source", "Source", "cyan"),
            ("valid_from", "Valid From", None),
            ("valid_until", "Valid Until", None),
            ("intent_count", "Intents", "green"),
        ]

        formatter.print_table(
            plan_data,
            columns,
            title=f"Plans for {resolved_date}",
            total_label="plan(s)" if plan_data else None,
        )

        if not plan_data and not json_output:
            formatter.print_message(f"No plans found for {resolved_date}.", "yellow")

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error listing plans: {e}", err=True)
        raise typer.Exit(1)

@app.command()
def remotes(ctx: typer.Context):
    """
    Show the available plan remotes.
    """
    ws: Workspace = ctx.obj
    remotes = ws.plans.remotes()
    typer.echo(f"Found {len(remotes)} configured plan remote(s):")
    for remote in remotes:
        typer.echo(f"- {remote.id} {remote.__class__.__name__}")

@app.command()
def show(
    ctx: typer.Context,
    source: str = typer.Argument(..., help="Plan source name (e.g., 'local', 'element')"),
    date: Optional[str] = typer.Argument(None, help="Date to show plan for (defaults to today)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    plain_output: bool = typer.Option(False, "--plain", help="Output as plain text (no colors)"),
):
    """
    Show detailed information about a specific plan.

    Displays the full plan including all intents, roles, objectives, actions, subjects, and trackers.

    Examples:
        faff plan show local
        faff plan show element
        faff plan show element yesterday
        faff plan show local --json
    """
    try:
        ws: Workspace = ctx.obj
        resolved_date = ws.parse_natural_date(date)

        plans = ws.plans.get_plans(resolved_date)

        if source not in plans:
            typer.echo(f"Error: No plan found with source '{source}' for {resolved_date}.", err=True)
            typer.echo(f"\nAvailable sources: {', '.join(plans.keys())}", err=True)
            raise typer.Exit(1)

        plan = plans[source]

        if json_output:
            # Output as JSON
            import json
            plan_dict = {
                "source": plan.source,
                "valid_from": str(plan.valid_from),
                "valid_until": str(plan.valid_until) if plan.valid_until else None,
                "intents": [
                    {
                        "intent_id": intent.intent_id,
                        "alias": intent.alias,
                        "role": intent.role,
                        "objective": intent.objective,
                        "action": intent.action,
                        "subject": intent.subject,
                        "trackers": list(intent.trackers) if intent.trackers else [],
                    }
                    for intent in plan.intents
                ],
            }
            typer.echo(json.dumps(plan_dict, indent=2))
        elif plain_output:
            # Output as plain TOML
            typer.echo(plan.to_toml())
        else:
            # Rich formatted output
            from rich.console import Console
            from rich.syntax import Syntax

            console = Console()
            console.print(f"\n[bold cyan]Plan: {plan.source}[/bold cyan]")
            console.print(f"[dim]Valid from {plan.valid_from}{' to ' + str(plan.valid_until) if plan.valid_until else ' onwards'}[/dim]")
            console.print(f"[dim]Intents: {len(plan.intents)}[/dim]\n")

            # Show as TOML with syntax highlighting
            toml_content = plan.to_toml()
            syntax = Syntax(toml_content, "toml", theme="monokai", line_numbers=False)
            console.print(syntax)

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error showing plan: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)

@app.command()
def trackers(
    ctx: typer.Context,
    date: str = typer.Argument(None, help="Date to get trackers for (defaults to today)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    plain_output: bool = typer.Option(False, "--plain", help="Output as plain text (no colors)"),
):
    """
    List all available trackers from plans.

    Shows all trackers defined in active plans, regardless of usage.

    Examples:
        faff plan trackers
        faff plan trackers yesterday
        faff plan trackers --json
    """
    try:
        ws: Workspace = ctx.obj
        resolved_date = ws.parse_natural_date(date)

        # Get all trackers from plans
        trackers_dict = ws.plans.get_trackers(resolved_date)

        if json_output:
            import json
            typer.echo(json.dumps(trackers_dict, indent=2))
        elif plain_output:
            # TSV format: ID\tName
            for tracker_id, name in sorted(trackers_dict.items()):
                typer.echo(f"{tracker_id}\t{name}")
        else:
            # Rich formatted output
            from faff_cli.output import create_formatter

            tracker_data = [
                {"id": tracker_id, "name": name}
                for tracker_id, name in sorted(trackers_dict.items())
            ]

            formatter = create_formatter(json_output, plain_output)
            columns = [
                ("id", "ID", "cyan"),
                ("name", "Name", "yellow"),
            ]

            formatter.print_table(
                tracker_data,
                columns,
                title="Available Trackers",
                total_label="tracker(s)" if tracker_data else None,
            )

            if not tracker_data:
                typer.echo("No trackers found in active plans.")

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error listing trackers: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


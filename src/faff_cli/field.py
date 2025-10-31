import typer
import toml
from pathlib import Path
from typing import List, Set
from collections import defaultdict

from rich.console import Console

from faff_core import Workspace

app = typer.Typer(help="Manage ROAST fields (roles, objectives, actions, subjects, trackers)")

VALID_FIELDS = ["role", "objective", "action", "subject", "tracker"]
PLURAL_MAP = {
    "role": "roles",
    "objective": "objectives",
    "action": "actions",
    "subject": "subjects",
    "tracker": "trackers",
}


@app.command()
def list(
    ctx: typer.Context,
    field: str = typer.Argument(..., help="Field to list (role, objective, action, subject, tracker)"),
):
    """
    List all unique values for a ROAST field across all plans.

    Shows field values from both plan-level collections and intents, with usage counts.
    """
    if field not in VALID_FIELDS:
        typer.echo(f"Error: field must be one of: {', '.join(VALID_FIELDS)}", err=True)
        raise typer.Exit(1)

    try:
        ws: Workspace = ctx.obj
        console = Console()

        # Get all plan files
        plan_dir = Path(ws.storage().plan_dir())
        plan_files = sorted(plan_dir.glob("*.toml"))

        # Collect all unique values with detailed counts
        values: Set[str] = set()
        intent_count = defaultdict(int)
        session_count = defaultdict(int)
        log_count = defaultdict(set)  # Set of log dates per value

        plural_field = PLURAL_MAP[field]

        # Count intents in plans
        for plan_file in plan_files:
            try:
                plan_data = toml.load(plan_file)

                # Get values from intents
                for intent_dict in plan_data.get("intents", []):
                    if field == "tracker":
                        intent_values = intent_dict.get("trackers", [])
                    else:
                        intent_value = intent_dict.get(field)
                        intent_values = [intent_value] if intent_value else []

                    for value in intent_values:
                        if value:
                            values.add(value)
                            intent_count[value] += 1

            except Exception:
                continue

        # Count sessions in logs
        log_dir = Path(ws.storage().log_dir())
        log_files = sorted(log_dir.glob("*.toml"))

        for log_file in log_files:
            try:
                log_data = toml.load(log_file)
                log_date = log_file.stem  # Use filename as identifier

                # Sessions are stored as timeline entries with flattened intent fields
                for session in log_data.get("timeline", []):
                    if field == "tracker":
                        # Trackers can be a string or list
                        trackers = session.get("trackers", [])
                        if isinstance(trackers, str):
                            session_values = [trackers]
                        else:
                            session_values = trackers
                    else:
                        session_value = session.get(field)
                        session_values = [session_value] if session_value else []

                    for value in session_values:
                        if value:
                            values.add(value)
                            session_count[value] += 1
                            log_count[value].add(log_date)

            except Exception:
                continue

        # Display results
        if not values:
            console.print(f"[yellow]No {plural_field} found[/yellow]")
            return

        console.print(f"[bold]{plural_field.title()}:[/bold]\n")
        for value in sorted(values):
            intents = intent_count.get(value, 0)
            sessions = session_count.get(value, 0)
            logs = len(log_count.get(value, set()))

            console.print(
                f"  {value} [dim]({intents} intent{'s' if intents != 1 else ''}, "
                f"{sessions} session{'s' if sessions != 1 else ''}, "
                f"{logs} log{'s' if logs != 1 else ''})[/dim]"
            )

        console.print(f"\n[bold]Total:[/bold] {len(values)} unique {plural_field}")

    except Exception as e:
        typer.echo(f"Error listing {plural_field}: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


@app.command()
def replace(
    ctx: typer.Context,
    field: str = typer.Argument(..., help="Field to replace (role, objective, action, subject)"),
    old_value: str = typer.Argument(..., help="Old value to replace"),
    new_value: str = typer.Argument(..., help="New value"),
):
    """
    Replace a field value across all plans and logs.

    This will:
    - Update the field in plan-level ROAST collections
    - Update all intents that use the old value
    - Update all log sessions that reference those intents
    """
    if field not in VALID_FIELDS:
        typer.echo(f"Error: field must be one of: {', '.join(VALID_FIELDS)}", err=True)
        raise typer.Exit(1)

    if field == "tracker":
        typer.echo("Error: tracker replacement not yet supported (trackers are key-value pairs)", err=True)
        raise typer.Exit(1)

    try:
        ws: Workspace = ctx.obj
        console = Console()

        plural_field = PLURAL_MAP[field]

        # Get all plan files
        plan_dir = Path(ws.storage().plan_dir())
        plan_files = sorted(plan_dir.glob("*.toml"))

        plans_updated = 0
        intents_updated = 0

        # Update plans
        for plan_file in plan_files:
            try:
                plan_data = toml.load(plan_file)
                plan_modified = False

                # Update plan-level ROAST collection
                if plural_field in plan_data:
                    field_list = plan_data[plural_field]
                    if old_value in field_list:
                        # Replace in list
                        field_list = [new_value if v == old_value else v for v in field_list]
                        plan_data[plural_field] = field_list
                        plan_modified = True

                # Update intents
                if "intents" in plan_data:
                    for intent_dict in plan_data["intents"]:
                        if intent_dict.get(field) == old_value:
                            intent_dict[field] = new_value
                            intents_updated += 1
                            plan_modified = True

                # Write back if modified
                if plan_modified:
                    with open(plan_file, 'w') as f:
                        toml.dump(plan_data, f)
                    plans_updated += 1

            except Exception as e:
                console.print(f"[yellow]Warning: Failed to update {plan_file.name}: {e}[/yellow]")
                continue

        console.print(f"[green]Updated {intents_updated} intent(s) across {plans_updated} plan(s)[/green]")

        # Now update logs (do this regardless of whether intents were updated)

        log_dir = Path(ws.storage().log_dir())
        log_files = sorted(log_dir.glob("*.toml"))

        logs_updated = 0
        sessions_updated = 0

        for log_file in log_files:
            try:
                log_data = toml.load(log_file)
                log_modified = False

                # Sessions are stored as timeline entries with flattened intent fields
                if "timeline" in log_data:
                    for session in log_data["timeline"]:
                        if session.get(field) == old_value:
                            session[field] = new_value
                            sessions_updated += 1
                            log_modified = True

                if log_modified:
                    with open(log_file, 'w') as f:
                        toml.dump(log_data, f)
                    logs_updated += 1

            except Exception as e:
                console.print(f"[yellow]Warning: Failed to update {log_file.name}: {e}[/yellow]")
                continue

        console.print(f"[green]Updated {sessions_updated} session(s) across {logs_updated} log(s)[/green]")

        console.print(f"\n[bold green]✓ Replacement complete[/bold green]")

    except Exception as e:
        typer.echo(f"Error replacing {field}: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)

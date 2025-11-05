import typer
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

        plural_field = PLURAL_MAP[field]

        # Get intent counts from plans via Rust
        intent_count = ws.plans.get_field_usage_stats(field)

        # Get session counts and log dates from logs via Rust
        session_count, log_dates_dict = ws.logs.get_field_usage_stats(field)

        # Combine all unique values from both plans and logs
        values = set(intent_count.keys()) | set(session_count.keys())

        # Convert log_dates_dict values (lists of PyDate) to count of unique logs
        log_count = {}
        for value, dates in log_dates_dict.items():
            log_count[value] = len(dates)

        # Display results
        if not values:
            console.print(f"[yellow]No {plural_field} found[/yellow]")
            return

        console.print(f"[bold]{plural_field.title()}:[/bold]\n")
        for value in sorted(values):
            intents = intent_count.get(value, 0)
            sessions = session_count.get(value, 0)
            logs = log_count.get(value, 0)

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

        # Update plans via Rust layer
        plans_updated, intents_updated = ws.plans.replace_field_in_all_plans(
            field, old_value, new_value
        )
        console.print(f"[green]Updated {intents_updated} intent(s) across {plans_updated} plan(s)[/green]")

        # Update logs via Rust layer
        import datetime
        trackers = ws.plans.get_trackers(datetime.date.today())
        logs_updated, sessions_updated = ws.logs.replace_field_in_all_logs(
            field, old_value, new_value, trackers
        )
        console.print(f"[green]Updated {sessions_updated} session(s) across {logs_updated} log(s)[/green]")

        console.print(f"\n[bold green]✓ Replacement complete[/bold green]")

    except Exception as e:
        typer.echo(f"Error replacing {field}: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)

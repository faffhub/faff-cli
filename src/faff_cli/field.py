import typer
from typing import List, Optional, Sequence
from rich.console import Console

from faff_core import Workspace
from faff_cli.output import create_formatter
from faff_cli.filtering import parse_simple_filters, apply_filters

app = typer.Typer(help="Manage ASTRO fields (actions, subjects, trackers, roles, objectives)")

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
    List unique values for a ASTRO field.

    Shows field values from both plan-level collections and intents, with usage counts.
    Results are sorted by usage (most used first).

    Examples:
        faff field list role
        faff field list action value~meeting
        faff field list role intents>10
        faff field list objective --json
    """
    if field not in VALID_FIELDS:
        typer.echo(f"Error: field must be one of: {', '.join(VALID_FIELDS)}", err=True)
        raise typer.Exit(1)

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

        plural_field = PLURAL_MAP[field]

        # Get all defined values from plans
        today = ws.today()
        if field == "role":
            all_defined = set(ws.plans.get_roles(today))
        elif field == "objective":
            all_defined = set(ws.plans.get_objectives(today))
        elif field == "action":
            all_defined = set(ws.plans.get_actions(today))
        elif field == "subject":
            all_defined = set(ws.plans.get_subjects(today))
        elif field == "tracker":
            all_defined = set(ws.plans.get_trackers(today).keys())
        else:
            all_defined = set()

        # Get intent counts from plans via Rust
        intent_count = ws.plans.get_field_usage_stats(field)

        # Get session counts and log dates from logs via Rust
        session_count, log_dates_dict = ws.logs.get_field_usage_stats(field)

        # Combine all values: defined in plans + used in intents/sessions
        values = all_defined | set(intent_count.keys()) | set(session_count.keys())

        # Convert log_dates_dict values (lists of PyDate) to count of unique logs
        log_count = {}
        for value, dates in log_dates_dict.items():
            log_count[value] = len(dates)

        # Get tracker names if listing trackers
        tracker_names = {}
        if field == "tracker":
            tracker_names = ws.plans.get_trackers(ws.today())

        # Build field data list
        field_data = []
        for value in values:
            intents = intent_count.get(value, 0)
            sessions = session_count.get(value, 0)
            logs = log_count.get(value, 0)

            row = {
                "value": value,
                "intents": intents,
                "sessions": sessions,
                "logs": logs,
            }

            # Add name for trackers
            if field == "tracker":
                row["name"] = tracker_names.get(value, "")

            field_data.append(row)

        # Apply filters
        if filters:
            field_data = apply_filters(field_data, filters)

        # Sort by usage (most used first = most sessions)
        field_data.sort(key=lambda x: (x["sessions"], x["intents"], x["logs"]), reverse=True)

        # Apply limit
        if limit:
            field_data = field_data[:limit]

        # Create output formatter
        formatter = create_formatter(json_output, plain_output)

        # Define columns for table output
        columns: Sequence[tuple[str, str, Optional[str]]]
        if field == "tracker":
            columns = [
                ("value", "Value", "cyan"),
                ("name", "Name", "yellow"),
                ("intents", "Intents", "green"),
                ("sessions", "Sessions", "green"),
                ("logs", "Logs", "green"),
            ]
        else:
            columns = [
                ("value", "Value", "cyan"),
                ("intents", "Intents", "green"),
                ("sessions", "Sessions", "green"),
                ("logs", "Logs", "green"),
            ]

        # Output results
        formatter.print_table(
            field_data,
            columns,
            title=plural_field.title(),
            total_label=f"unique {plural_field}" if field_data else None,
        )

        if not field_data and not json_output:
            formatter.print_message(f"No {plural_field} found matching criteria.", "yellow")

    except typer.Exit:
        raise
    except Exception as e:
        plural_field = PLURAL_MAP.get(field, field)
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
    - Update the field in plan-level ASTRO collections
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

        console.print("\n[bold green]✓ Replacement complete[/bold green]")

    except Exception as e:
        typer.echo(f"Error replacing {field}: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)

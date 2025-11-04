import typer
import toml
import tempfile
from pathlib import Path
from typing import Optional, List

from rich.table import Table
from rich.console import Console
from rich.markup import escape

from faff_cli.utils import edit_file

from faff_core import Workspace, Filter
from faff_core.models import Intent

app = typer.Typer(help="Manage intents (edit, derive, etc.)")


def intent_to_toml(intent: Intent) -> str:
    """Convert an intent to TOML format for editing."""
    intent_dict = {}

    # Only include intent_id if it's not empty
    if intent.intent_id:
        intent_dict["intent_id"] = intent.intent_id

    intent_dict.update({
        "alias": intent.alias,
        "role": intent.role,
        "objective": intent.objective,
        "action": intent.action,
        "subject": intent.subject,
        "trackers": list(intent.trackers) if intent.trackers else []
    })
    return toml.dumps(intent_dict)


def toml_to_intent(toml_str: str) -> Intent:
    """Parse an intent from TOML format."""
    intent_dict = toml.loads(toml_str)
    return Intent(
        intent_id=intent_dict.get("intent_id", ""),
        alias=intent_dict.get("alias"),
        role=intent_dict.get("role"),
        objective=intent_dict.get("objective"),
        action=intent_dict.get("action"),
        subject=intent_dict.get("subject"),
        trackers=intent_dict.get("trackers", [])
    )


def edit_intent_in_editor(intent: Intent) -> Optional[Intent]:
    """
    Open the intent in the user's editor for editing.

    Returns:
        Updated Intent if changes were made, None if no changes
    """
    # Create a temporary file with the intent as TOML
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write(intent_to_toml(intent))
        temp_path = Path(f.name)

    try:
        # Open in editor
        if edit_file(temp_path):
            # Parse the edited content
            edited_intent = toml_to_intent(temp_path.read_text())
            return edited_intent
        else:
            return None
    finally:
        # Clean up temp file
        temp_path.unlink(missing_ok=True)


def format_field(value: str) -> str:
    """Format a field with source prefix dimmed and content bold."""
    if ":" in value:
        prefix, content = value.split(":", 1)
        return f"[dim]{prefix}:[/dim][bold]{content}[/bold]"
    return f"[bold]{value}[/bold]"


def display_intents_compact(intents: List[dict], console: Console) -> None:
    """Display intents in compact multi-line format."""
    for intent_info in intents:
        # First line: ID alias (usage) valid dates
        valid_str = str(intent_info["valid_from"])
        if intent_info["valid_until"]:
            valid_str += f" → {intent_info['valid_until']}"
        else:
            valid_str += " →"

        # Escape intent_id and alias to prevent Rich from styling them
        intent_id_escaped = escape(intent_info['intent_id'])
        alias_escaped = escape(intent_info['alias'])

        # Get usage stats
        sessions = intent_info.get("session_count", 0)
        logs = intent_info.get("log_count", 0)
        usage_str = f"({sessions} session{'s' if sessions != 1 else ''}, {logs} log{'s' if logs != 1 else ''})"

        console.print(
            f"[cyan]{intent_id_escaped}[/cyan]  "
            f"[yellow]{alias_escaped}[/yellow]  "
            f"[dim]{usage_str}[/dim]  "
            f"[dim]{valid_str}[/dim]"
        )

        # Second line: As <role> I do <action> to achieve <objective> for <subject>
        role_fmt = format_field(intent_info['role'])
        action_fmt = format_field(intent_info['action'])
        objective_fmt = format_field(intent_info['objective'])
        subject_fmt = format_field(intent_info['subject'])

        console.print(
            f"  As {role_fmt} "
            f"I do {action_fmt} "
            f"to achieve {objective_fmt} "
            f"for {subject_fmt}"
        )
        console.print()  # Blank line between intents


def display_intents_table(intents: List[dict], console: Console) -> None:
    """Display intents in table format."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("Intent ID", style="cyan")
    table.add_column("Alias", style="green")
    table.add_column("Role")
    table.add_column("Objective")
    table.add_column("Action")
    table.add_column("Subject")
    table.add_column("Trackers")
    table.add_column("Valid From")
    table.add_column("Valid Until")

    for intent_info in intents:
        table.add_row(
            intent_info["intent_id"],
            intent_info["alias"],
            intent_info["role"],
            intent_info["objective"],
            intent_info["action"],
            intent_info["subject"],
            intent_info["trackers"],
            str(intent_info["valid_from"]),
            intent_info["valid_until"] or "∞",
        )

    console.print(table)


def matches_filter(intent_info: dict, filter_obj: Filter) -> bool:
    """Check if an intent matches the given filter."""
    field = filter_obj.field()
    value = intent_info.get(field, "")
    filter_value = filter_obj.value()
    operator = filter_obj.operator()

    # Handle different filter types
    if operator == "=":
        return value == filter_value
    elif operator == "~":
        return filter_value.lower() in (value or "").lower()
    elif operator == "!=":
        return value != filter_value

    return True


@app.command(name="list")
def ls(
    ctx: typer.Context,
    filter_strings: List[str] = typer.Argument(
        None,
        help="Filters in the form key=value, key~value, or key!=value (e.g. alias~sync, role=element:head-of-customer-success).",
    ),
    table: bool = typer.Option(
        False,
        "--table",
        help="Display in table format instead of compact format",
    ),
):
    """
    List all intents from all plans.

    Supports filtering using the same syntax as faff query:
    - key=value (exact match)
    - key~value (contains match)
    - key!=value (not equal)

    Supported fields: intent_id, alias, role, objective, action, subject, trackers, source
    """
    try:
        ws: Workspace = ctx.obj

        # Parse filters
        filters = [Filter.parse(f) for f in filter_strings] if filter_strings else []

        # Get all plan files
        plan_dir = Path(ws.storage().plan_dir())
        plan_files = sorted(plan_dir.glob("*.toml"))

        # Collect all intents with their plan metadata
        all_intents = []
        for plan_file in plan_files:
            try:
                plan_data = toml.load(plan_file)
                source = plan_data.get("source", "unknown")
                valid_from = plan_data.get("valid_from", "unknown")
                valid_until = plan_data.get("valid_until", "")

                for intent_dict in plan_data.get("intents", []):
                    intent_info = {
                        "intent_id": intent_dict.get("intent_id", ""),
                        "alias": intent_dict.get("alias", ""),
                        "role": intent_dict.get("role", ""),
                        "objective": intent_dict.get("objective", ""),
                        "action": intent_dict.get("action", ""),
                        "subject": intent_dict.get("subject", ""),
                        "trackers": ", ".join(intent_dict.get("trackers", [])),
                        "source": source,
                        "valid_from": valid_from,
                        "valid_until": valid_until,
                    }
                    all_intents.append(intent_info)
            except Exception:
                continue

        # Count sessions per intent ID across all logs
        from collections import defaultdict
        session_count: dict[str, int] = defaultdict(int)
        log_count: dict[str, set[str]] = defaultdict(set)

        log_dir = Path(ws.storage().log_dir())
        log_files = sorted(log_dir.glob("*.toml"))

        for log_file in log_files:
            try:
                log_data = toml.load(log_file)
                log_date = log_file.stem

                for session in log_data.get("timeline", []):
                    intent_id = session.get("intent_id")
                    if intent_id:
                        session_count[intent_id] += 1
                        log_count[intent_id].add(log_date)
            except Exception:
                continue

        # Add usage stats to each intent
        for intent_info in all_intents:
            intent_id = intent_info["intent_id"]
            intent_info["session_count"] = session_count.get(intent_id, 0)
            intent_info["log_count"] = len(log_count.get(intent_id, set()))

        # Apply filters
        filtered_intents = []
        for intent_info in all_intents:
            # Check all filters (AND logic)
            if all(matches_filter(intent_info, f) for f in filters):
                filtered_intents.append(intent_info)

        # Sort by session count (most used first)
        filtered_intents.sort(key=lambda x: x.get("session_count", 0), reverse=True)

        # Display results (disable auto-highlighting to prevent unwanted styling)
        console = Console(highlight=False)
        if table:
            display_intents_table(filtered_intents, console)
        else:
            display_intents_compact(filtered_intents, console)

        console.print(f"[bold]Total:[/bold] {len(filtered_intents)} intent(s)")

    except Exception as e:
        typer.echo(f"Error listing intents: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


@app.command()
def replace(ctx: typer.Context, old_intent_id: str, new_intent_id: str):
    """
    Replace all uses of one intent with another.

    This is useful for:
    - Fixing orphaned intents
    - Consolidating duplicate intents
    - Migrating from deprecated intents

    After replacement, all sessions using old_intent_id will be updated to
    use new_intent_id. The old intent remains in plans but won't be used
    by any sessions.
    """
    try:
        ws: Workspace = ctx.obj

        # Verify both intents exist
        old_result = ws.plans.find_intent_by_id(old_intent_id)
        new_result = ws.plans.find_intent_by_id(new_intent_id)

        # Old intent might be orphaned (not in any plan), so check logs if not found in plans
        if not old_result:
            typer.echo(f"Warning: Old intent '{old_intent_id}' not found in any plan.")
            typer.echo("It may be orphaned. Checking logs...")

            # Check if it's used in logs
            logs_with_old = ws.logs.find_logs_with_intent(old_intent_id)
            if not logs_with_old:
                typer.echo(f"Error: Old intent '{old_intent_id}' not found in plans or logs.", err=True)
                raise typer.Exit(1)

            typer.echo(f"✓ Found {len(logs_with_old)} log file(s) using orphaned old intent.")
            old_alias = "Unknown (orphaned)"
        else:
            old_source, old_intent, _ = old_result
            old_alias = old_intent.alias
            typer.echo(f"✓ Found old intent: {old_alias} (from '{old_source}' plan)")

        if not new_result:
            typer.echo(f"Error: New intent '{new_intent_id}' not found.", err=True)
            raise typer.Exit(1)

        new_source, new_intent, _ = new_result
        typer.echo(f"✓ Found new intent: {new_intent.alias} (from '{new_source}' plan)")

        # Find all sessions using the old intent
        typer.echo(f"\nSearching for sessions using old intent...")
        logs_with_old = ws.logs.find_logs_with_intent(old_intent_id)

        if not logs_with_old:
            typer.echo(f"\n✓ No sessions found using old intent '{old_intent_id}'.")
            typer.echo("Nothing to replace.")
            return

        total_sessions = sum(count for _, count in logs_with_old)
        typer.echo(f"\n{'='*60}")
        typer.echo("REPLACEMENT SUMMARY")
        typer.echo('='*60)
        typer.echo(f"Old intent: {old_alias} ({old_intent_id})")
        typer.echo(f"New intent: {new_intent.alias} ({new_intent_id})")
        typer.echo(f"\nWill update {total_sessions} session(s) across {len(logs_with_old)} log file(s):")
        for date, count in logs_with_old[:5]:  # Show first 5
            typer.echo(f"  - {date}: {count} session(s)")
        if len(logs_with_old) > 5:
            typer.echo(f"  ... and {len(logs_with_old) - 5} more")
        typer.echo('='*60 + "\n")

        if not typer.confirm("Proceed with replacement?", default=False):
            typer.echo("Cancelled.")
            return

        # Perform the replacement
        typer.echo("\nReplacing sessions...")
        trackers = ws.plans.get_trackers(ws.today())
        total_updated = ws.logs.update_intent_in_logs(
            old_intent_id,
            new_intent,
            trackers
        )

        typer.echo(f"\n✓ Successfully replaced {total_updated} session(s).")
        typer.echo(f"\nAll sessions now use: {new_intent.alias} ({new_intent_id})")

        if old_result:
            typer.echo(f"\nNote: Old intent remains in '{old_source}' plan but is no longer used.")
            typer.echo("You may want to remove it manually if it's no longer needed.")

    except Exception as e:
        typer.echo(f"Error replacing intents: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def derive(ctx: typer.Context, intent_id: str):
    """
    Create a new intent derived from an existing one.

    The derived intent will be added to today's local plan and will be
    available from today onwards. The original intent remains unchanged.
    """
    try:
        ws: Workspace = ctx.obj

        # Find the source intent using Rust
        result = ws.plans.find_intent_by_id(intent_id)
        if not result:
            typer.echo(f"Error: Intent with ID '{intent_id}' not found.", err=True)
            raise typer.Exit(1)

        source, original_intent, plan_file_path = result

        typer.echo(f"Found intent in '{source}' plan ({Path(plan_file_path).name})")
        typer.echo(f"Creating a derived intent based on: {original_intent.alias}")

        # Save the original intent_id for the summary display
        original_intent_id = original_intent.intent_id

        # Create a new Intent without the intent_id for editing
        # (Intent objects are immutable, so we can't modify in place)
        # A new ID will be generated when the intent is added to a plan
        template_intent = Intent(
            intent_id="",
            alias=original_intent.alias,
            role=original_intent.role,
            objective=original_intent.objective,
            action=original_intent.action,
            subject=original_intent.subject,
            trackers=original_intent.trackers
        )

        # Edit the intent in the editor
        derived_intent = edit_intent_in_editor(template_intent)

        if not derived_intent:
            typer.echo("\nNo changes made. Cancelled.")
            return

        # Show changes summary
        typer.echo("\n" + "="*60)
        typer.echo("DERIVED INTENT SUMMARY")
        typer.echo("="*60)
        typer.echo(f"Source intent: {original_intent.alias} ({original_intent_id})")
        typer.echo(f"New alias: {derived_intent.alias}")
        if derived_intent.role != original_intent.role:
            typer.echo(f"Role: {original_intent.role} → {derived_intent.role}")
        if derived_intent.objective != original_intent.objective:
            typer.echo(f"Objective: {original_intent.objective} → {derived_intent.objective}")
        if derived_intent.action != original_intent.action:
            typer.echo(f"Action: {original_intent.action} → {derived_intent.action}")
        if derived_intent.subject != original_intent.subject:
            typer.echo(f"Subject: {original_intent.subject} → {derived_intent.subject}")
        if derived_intent.trackers != original_intent.trackers:
            typer.echo(f"Trackers: {original_intent.trackers} → {derived_intent.trackers}")
        typer.echo("="*60 + "\n")

        if not typer.confirm("Create this derived intent?"):
            typer.echo("Cancelled.")
            return

        # Add to today's local plan
        today = ws.today()
        local_plan = ws.plans.get_local_plan_or_create(today)
        new_plan = local_plan.add_intent(derived_intent)
        ws.plans.write_plan(new_plan)

        typer.echo(f"\n✓ Created derived intent with ID: {new_plan.intents[-1].intent_id}")
        typer.echo(f"✓ Added to local plan for {today}")
        typer.echo("\nThe derived intent is now available for use from today onwards.")
        typer.echo("The original intent remains unchanged in its plan.")

    except Exception as e:
        typer.echo(f"Error deriving intent: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def edit(ctx: typer.Context, intent_id: str):
    """
    Edit an existing intent.

    After editing, you'll be asked whether to apply changes retroactively
    to all past sessions or cancel.
    """
    try:
        ws: Workspace = ctx.obj

        # Find the intent using Rust
        result = ws.plans.find_intent_by_id(intent_id)
        if not result:
            typer.echo(f"Error: Intent with ID '{intent_id}' not found.", err=True)
            raise typer.Exit(1)

        source, original_intent, plan_file_path = result

        typer.echo(f"Found intent in '{source}' plan ({Path(plan_file_path).name})")

        # Check if it's a local intent (can edit) by checking the ID prefix
        if not original_intent.intent_id.startswith("local:"):
            typer.echo(f"\nError: This intent is from a remote source.")
            typer.echo(f"Intent ID: {original_intent.intent_id}")
            typer.echo("Remote intents cannot be edited directly.")
            typer.echo("You can use 'faff intent derive' to create a local copy instead.")
            raise typer.Exit(1)

        # Edit the intent in the editor
        updated_intent = edit_intent_in_editor(original_intent)

        if not updated_intent:
            typer.echo("\nNo changes made.")
            return

        # Show changes summary
        typer.echo("\n" + "="*60)
        typer.echo("CHANGES SUMMARY")
        typer.echo("="*60)
        if updated_intent.alias != original_intent.alias:
            typer.echo(f"Alias: {original_intent.alias} → {updated_intent.alias}")
        if updated_intent.role != original_intent.role:
            typer.echo(f"Role: {original_intent.role} → {updated_intent.role}")
        if updated_intent.objective != original_intent.objective:
            typer.echo(f"Objective: {original_intent.objective} → {updated_intent.objective}")
        if updated_intent.action != original_intent.action:
            typer.echo(f"Action: {original_intent.action} → {updated_intent.action}")
        if updated_intent.subject != original_intent.subject:
            typer.echo(f"Subject: {original_intent.subject} → {updated_intent.subject}")
        if updated_intent.trackers != original_intent.trackers:
            typer.echo(f"Trackers: {original_intent.trackers} → {updated_intent.trackers}")
        typer.echo("="*60 + "\n")

        if not typer.confirm("Apply these changes?"):
            typer.echo("Cancelled.")
            return

        # Check if any sessions use this intent using Rust
        typer.echo("\nSearching for sessions using this intent...")
        logs_with_intent = ws.logs.find_logs_with_intent(original_intent.intent_id)

        if logs_with_intent:
            total_sessions = sum(count for _, count in logs_with_intent)
            typer.echo(f"\n⚠️  This intent is used in {total_sessions} session(s) across {len(logs_with_intent)} log file(s):")
            for date, count in logs_with_intent[:5]:  # Show first 5
                typer.echo(f"  - {date}: {count} session(s)")
            if len(logs_with_intent) > 5:
                typer.echo(f"  ... and {len(logs_with_intent) - 5} more")

            typer.echo("\n⚠️  Editing will apply changes retroactively to ALL sessions.")
            typer.echo("\nIf you want to change behavior going forward while preserving history,")
            typer.echo("use 'faff intent derive' instead to create a new intent based on this one.")

            if not typer.confirm("\nApply changes retroactively?", default=False):
                typer.echo("Cancelled.")
                return

            apply_retroactive = True
        else:
            typer.echo("\n✓ No sessions found using this intent.")
            apply_retroactive = False

        # Update the plan file using Rust
        typer.echo("\nUpdating plan...")
        ws.plans.update_intent_by_id(original_intent.intent_id, updated_intent)
        typer.echo(f"✓ Updated intent in {Path(plan_file_path).name}")

        # Apply retroactive updates if requested using Rust
        if apply_retroactive:
            typer.echo("\nUpdating log files...")
            trackers = ws.plans.get_trackers(ws.today())
            total_updated = ws.logs.update_intent_in_logs(
                original_intent.intent_id,
                updated_intent,
                trackers
            )
            typer.echo(f"\n✓ Updated {total_updated} session(s) in {len(logs_with_intent)} log file(s)")

        typer.echo("\nIntent updated successfully!")

    except Exception as e:
        typer.echo(f"Error editing intent: {e}", err=True)
        raise typer.Exit(1)

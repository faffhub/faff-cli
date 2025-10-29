import typer
import toml
import tempfile
from pathlib import Path
from typing import Optional

from faff_cli.utils import edit_file

from faff_core import Workspace
from faff_core.models import Intent

app = typer.Typer(help="Manage intents (edit, derive, etc.)")


def find_intent_in_plans(ws: Workspace, intent_id: str) -> Optional[tuple[str, Intent, Path]]:
    """
    Search all plans for an intent with the given ID.

    Returns:
        (source, intent, plan_file_path) tuple if found, None otherwise
    """
    plan_dir = Path(ws.storage().plan_dir())

    for plan_file in plan_dir.glob("*.toml"):
        try:
            plan_data = toml.load(plan_file)
            if "intents" not in plan_data:
                continue

            for intent_dict in plan_data["intents"]:
                if intent_dict.get("intent_id") == intent_id:
                    # Found it! Extract source from filename (source.date.toml)
                    source = plan_file.stem.split(".")[0]
                    intent = Intent(
                        intent_id=intent_dict.get("intent_id", ""),
                        alias=intent_dict.get("alias"),
                        role=intent_dict.get("role"),
                        objective=intent_dict.get("objective"),
                        action=intent_dict.get("action"),
                        subject=intent_dict.get("subject"),
                        trackers=intent_dict.get("trackers", [])
                    )
                    return (source, intent, plan_file)
        except Exception as e:
            # Skip files that can't be parsed
            continue

    return None


def intent_to_toml(intent: Intent) -> str:
    """Convert an intent to TOML format for editing."""
    intent_dict = {
        "intent_id": intent.intent_id,
        "alias": intent.alias,
        "role": intent.role,
        "objective": intent.objective,
        "action": intent.action,
        "subject": intent.subject,
        "trackers": list(intent.trackers) if intent.trackers else []
    }
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


def find_logs_using_intent(ws: Workspace, intent_id: str) -> list[tuple[Path, int]]:
    """
    Find all log files that contain sessions using the given intent.

    Returns:
        List of (log_file_path, session_count) tuples
    """
    log_dir = Path(ws.storage().log_dir())
    logs_with_intent = []

    for log_file in log_dir.glob("*.toml"):
        try:
            log_data = toml.load(log_file)
            if "timeline" not in log_data:
                continue

            # Count sessions using this intent
            session_count = sum(
                1 for session in log_data["timeline"]
                if session.get("intent_id") == intent_id
            )

            if session_count > 0:
                logs_with_intent.append((log_file, session_count))

        except Exception:
            # Skip files that can't be parsed
            continue

    return logs_with_intent


def update_intent_in_log(log_file: Path, intent_id: str, updated_intent: Intent) -> int:
    """
    Update all sessions in a log file that use the given intent.

    Returns:
        Number of sessions updated
    """
    log_data = toml.load(log_file)

    if "timeline" not in log_data:
        return 0

    updated_count = 0

    for session in log_data["timeline"]:
        if session.get("intent_id") == intent_id:
            # Update intent fields in the session
            session["alias"] = updated_intent.alias
            session["role"] = updated_intent.role
            session["objective"] = updated_intent.objective
            session["action"] = updated_intent.action
            session["subject"] = updated_intent.subject
            session["trackers"] = updated_intent.trackers[0] if updated_intent.trackers else ""
            updated_count += 1

    if updated_count > 0:
        # Write back to file
        with open(log_file, 'w') as f:
            toml.dump(log_data, f)

    return updated_count


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


@app.command()
def edit(ctx: typer.Context, intent_id: str):
    """
    Edit an existing intent.

    After editing, you'll be asked whether to:
    - Apply changes retroactively to all past sessions
    - Clone as a new intent (keeping old sessions unchanged)
    - Cancel
    """
    try:
        ws: Workspace = ctx.obj

        # Find the intent
        result = find_intent_in_plans(ws, intent_id)
        if not result:
            typer.echo(f"Error: Intent with ID '{intent_id}' not found.", err=True)
            raise typer.Exit(1)

        source, original_intent, plan_file = result

        typer.echo(f"Found intent in '{source}' plan ({plan_file.name})")

        # Check if it's a local intent (can edit) by checking the ID prefix
        if not original_intent.intent_id.startswith("local:"):
            typer.echo(f"\nError: This intent is from a remote source.")
            typer.echo(f"Intent ID: {original_intent.intent_id}")
            typer.echo("Remote intents cannot be edited directly.")
            typer.echo("You can use 'faff intent derive' to create a local copy instead.")
            raise typer.Exit(1)

        # Edit the intent in vim
        updated_intent = edit_intent_in_editor(original_intent)

        if not updated_intent:
            typer.echo("\nNo changes made.")
            return

        # TODO: Check if any sessions use this intent
        # For now, just update the plan

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

        # Check if any sessions use this intent
        typer.echo("\nSearching for sessions using this intent...")
        logs_with_intent = find_logs_using_intent(ws, original_intent.intent_id)

        if logs_with_intent:
            total_sessions = sum(count for _, count in logs_with_intent)
            typer.echo(f"\n⚠️  This intent is used in {total_sessions} session(s) across {len(logs_with_intent)} log file(s):")
            for log_file, count in logs_with_intent[:5]:  # Show first 5
                typer.echo(f"  - {log_file.stem}: {count} session(s)")
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

        # Update the plan file
        typer.echo("\nUpdating plan...")
        plan_data = toml.load(plan_file)

        for i, intent_dict in enumerate(plan_data.get("intents", [])):
            if intent_dict.get("intent_id") == original_intent.intent_id:
                plan_data["intents"][i] = {
                    "intent_id": updated_intent.intent_id,
                    "alias": updated_intent.alias,
                    "role": updated_intent.role,
                    "objective": updated_intent.objective,
                    "action": updated_intent.action,
                    "subject": updated_intent.subject,
                    "trackers": list(updated_intent.trackers) if updated_intent.trackers else []
                }
                break

        with open(plan_file, 'w') as f:
            toml.dump(plan_data, f)

        typer.echo(f"✓ Updated intent in {plan_file.name}")

        # Apply retroactive updates if requested
        if apply_retroactive:
            typer.echo("\nUpdating log files...")
            total_updated = 0
            for log_file, _ in logs_with_intent:
                count = update_intent_in_log(log_file, original_intent.intent_id, updated_intent)
                total_updated += count
                typer.echo(f"  ✓ {log_file.stem}: updated {count} session(s)")

            typer.echo(f"\n✓ Updated {total_updated} session(s) in {len(logs_with_intent)} log file(s)")

        typer.echo("\nIntent updated successfully!")

    except Exception as e:
        typer.echo(f"Error editing intent: {e}", err=True)
        raise typer.Exit(1)

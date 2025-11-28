import typer
import toml
import tempfile
from pathlib import Path
from typing import Optional, List

from rich.table import Table
from rich.console import Console
from rich.markup import escape

from faff_cli.utils import edit_file
from faff_cli.output import create_formatter
from faff_cli.filtering import FilterConfig, apply_filters
from faff_cli.ui import fuzzy_select
from faff_cli.ui.fuzzy_select import FuzzyItem
from faff_cli.start import nicer

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
    with tempfile.NamedTemporaryFile(mode='w', suffix='.faff.toml', delete=False) as f:
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
        # First line: ID alias (usage)
        # Escape intent_id and alias to prevent Rich from styling them
        intent_id_escaped = escape(intent_info['intent_id'] or "(no id)")
        alias_escaped = escape(intent_info['alias'] or "(no alias)")

        # Get usage stats
        sessions = intent_info.get("session_count", 0)
        logs = intent_info.get("log_count", 0)
        usage_str = f"({sessions} session{'s' if sessions != 1 else ''}, {logs} log{'s' if logs != 1 else ''})"

        console.print(
            f"[cyan]{intent_id_escaped}[/cyan]  "
            f"[yellow]{alias_escaped}[/yellow]  "
            f"[dim]{usage_str}[/dim]"
        )

        # Second line: As <role> I do <action> to achieve <objective> for <subject>
        # Only show if at least one field is present
        role = intent_info.get('role') or ""
        action = intent_info.get('action') or ""
        objective = intent_info.get('objective') or ""
        subject = intent_info.get('subject') or ""

        if role or action or objective or subject:
            role_fmt = format_field(role) if role else "[dim](no role)[/dim]"
            action_fmt = format_field(action) if action else "[dim](no action)[/dim]"
            objective_fmt = format_field(objective) if objective else "[dim](no objective)[/dim]"
            subject_fmt = format_field(subject) if subject else "[dim](no subject)[/dim]"

            console.print(
                f"  As {role_fmt} "
                f"I do {action_fmt} "
                f"to achieve {objective_fmt} "
                f"for {subject_fmt}"
            )
        else:
            console.print("  [dim](incomplete intent - no ASTRO fields)[/dim]")

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
    table.add_column("Sessions")
    table.add_column("Logs")

    for intent_info in intents:
        table.add_row(
            intent_info["intent_id"],
            intent_info["alias"],
            intent_info["role"],
            intent_info["objective"],
            intent_info["action"],
            intent_info["subject"],
            intent_info["trackers"],
            str(intent_info["session_count"]),
            str(intent_info["log_count"]),
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
    date: Optional[str] = typer.Argument(None, help="Date to list intents for (defaults to today)"),
    filter_strings: List[str] = typer.Argument(
        None,
        help="Filters: field=value (exact), field~value (contains), field!=value (not equal)",
    ),
    table: bool = typer.Option(
        False,
        "--table",
        help="Display in table format instead of compact format",
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
    List intents valid for a specific date.

    Shows usage statistics (session count, log count) and sorts by most used first.

    Supported filter fields: intent_id, alias, role, objective, action, subject, trackers

    Examples:
        faff intent list
        faff intent list 2025-06-15
        faff intent list yesterday alias~meeting
        faff intent list --table
        faff intent list --json
        faff intent list --limit 10
    """
    try:
        ws: Workspace = ctx.obj

        # Parse date argument
        if date:
            target_date = ws.parse_natural_date(date)
        else:
            target_date = ws.today()

        # Parse filters using unified filtering
        filter_config = FilterConfig(filter_strings=filter_strings)
        filters, _, _ = filter_config.get_all(ws)

        # Get intents valid for the target date using the API
        intents = ws.plans.get_intents(target_date)

        # Calculate usage statistics by reading all logs once
        from collections import defaultdict
        session_count = defaultdict(int)
        log_count = defaultdict(set)

        for log in ws.logs.list_logs():
            for session in log.timeline:
                intent_id = session.intent.intent_id
                session_count[intent_id] += 1
                log_count[intent_id].add(log.date)

        # Build intent info list with usage statistics
        all_intents = []
        for intent in intents:
            # Extract source from intent_id (format: "source:i-YYYYMMDD-xxxxx")
            source = intent.intent_id.split(":")[0] if ":" in intent.intent_id else "unknown"

            intent_info = {
                "intent_id": intent.intent_id or "",
                "alias": intent.alias or "(no alias)",
                "role": intent.role or "",
                "objective": intent.objective or "",
                "action": intent.action or "",
                "subject": intent.subject or "",
                "trackers": ", ".join(intent.trackers) if intent.trackers else "",
                "source": source,
                "valid_from": str(target_date),  # Valid on the target date
                "valid_until": "",  # Not showing end dates in this view
                "session_count": session_count.get(intent.intent_id, 0),
                "log_count": len(log_count.get(intent.intent_id, set())),
            }
            all_intents.append(intent_info)

        # Apply filters using unified filtering
        if filters:
            all_intents = apply_filters(all_intents, filters)

        # Sort by session count (most used first - usage-based data)
        all_intents.sort(key=lambda x: x.get("session_count", 0), reverse=True)

        # Apply limit
        if limit:
            all_intents = all_intents[:limit]

        # Output based on mode
        if json_output:
            # JSON output
            formatter = create_formatter(json_output=True)
            formatter.print_table(all_intents, [], title="Intents")
        elif plain_output:
            # Plain text output (tab-separated)
            formatter = create_formatter(plain_output=True)
            columns = [
                ("intent_id", "Intent ID", None),
                ("alias", "Alias", None),
                ("role", "Role", None),
                ("objective", "Objective", None),
                ("action", "Action", None),
                ("subject", "Subject", None),
                ("session_count", "Sessions", None),
                ("log_count", "Logs", None),
            ]
            formatter.print_table(all_intents, columns, total_label="intents")
        else:
            # Rich output (existing compact/table formats)
            console = Console(highlight=False)
            if table:
                display_intents_table(all_intents, console)
            else:
                display_intents_compact(all_intents, console)

            console.print(f"[bold]Total:[/bold] {len(all_intents)} intent(s)")

    except typer.Exit:
        raise
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
        typer.echo("\nSearching for sessions using old intent...")
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
            old_source_name, _, _ = old_result
            typer.echo(f"\nNote: Old intent remains in '{old_source_name}' plan but is no longer used.")
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
            typer.echo("\nError: This intent is from a remote source.")
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


@app.command()
def complete(
    ctx: typer.Context,
    intent_id: Optional[str] = typer.Argument(None, help="Intent ID to complete (if not provided, shows incomplete intents)")
):
    """
    Complete an intent by filling in missing fields interactively.

    This command helps you fill in fields that were skipped during 'faff start'.
    Only prompts for fields that are currently null/empty.
    """
    try:
        ws: Workspace = ctx.obj
        date = ws.today()

        # If no intent_id provided, find and show incomplete intents
        if not intent_id:
            all_intents = ws.plans.get_intents(date)
            incomplete_intents = [
                intent for intent in all_intents
                if not intent.role or not intent.objective or not intent.action or not intent.subject
            ]

            if not incomplete_intents:
                typer.echo("No incomplete intents found! All intents have all fields filled.")
                return

            typer.echo(f"\nFound {len(incomplete_intents)} incomplete intent(s):\n")

            # Show incomplete intents with missing fields highlighted
            for intent in incomplete_intents:
                missing = []
                if not intent.role:
                    missing.append("role")
                if not intent.objective:
                    missing.append("objective")
                if not intent.action:
                    missing.append("action")
                if not intent.subject:
                    missing.append("subject")

                typer.echo(f"  {intent.alias} ({intent.intent_id})")
                typer.echo(f"    Missing: {', '.join(missing)}\n")

            # Let user select which one to complete
            choices = [
                FuzzyItem(
                    name=f"{intent.alias} (missing: {', '.join([f for f in ['role', 'objective', 'action', 'subject'] if not getattr(intent, f)])})",
                    value=intent.intent_id,
                    decoration=intent.intent_id
                )
                for intent in incomplete_intents
            ]

            selected = fuzzy_select(
                "Which intent would you like to complete?",
                choices,
                escapable=True
            )

            if not selected:
                typer.echo("Cancelled.")
                return

            intent_id = selected.value

        # Find the intent
        result = ws.plans.find_intent_by_id(intent_id)
        if not result:
            typer.echo(f"Error: Intent with ID '{intent_id}' not found.", err=True)
            raise typer.Exit(1)

        source, original_intent, plan_file_path = result

        # Check if it's a local intent
        if not original_intent.intent_id.startswith("local:"):
            typer.echo("\nError: This intent is from a remote source.")
            typer.echo(f"Intent ID: {original_intent.intent_id}")
            typer.echo("Remote intents cannot be edited.")
            typer.echo("Use 'faff intent derive' to create a local copy instead.")
            raise typer.Exit(1)

        typer.echo(f"\nCompleting intent: {original_intent.alias}")
        typer.echo(f"From: {source} ({Path(plan_file_path).name})\n")

        # Prompt for missing fields only
        updated_fields = {}

        if not original_intent.role:
            role = fuzzy_select(
                "What job role are you playing in this activity?",
                nicer([x for x in ws.plans.get_roles(date)]),
                escapable=True
            )
            if role:
                updated_fields['role'] = role.value
                typer.echo(f"  ✓ Set role: {role.value}")
        else:
            typer.echo(f"  ✓ Role already set: {original_intent.role}")

        if not original_intent.objective:
            objective = fuzzy_select(
                "What is the main goal of this activity?",
                nicer([x for x in ws.plans.get_objectives(date)]),
                escapable=True
            )
            if objective:
                updated_fields['objective'] = objective.value
                typer.echo(f"  ✓ Set objective: {objective.value}")
        else:
            typer.echo(f"  ✓ Objective already set: {original_intent.objective}")

        if not original_intent.action:
            action = fuzzy_select(
                "What action are you doing?",
                nicer([x for x in ws.plans.get_actions(date)]),
                escapable=True
            )
            if action:
                updated_fields['action'] = action.value
                typer.echo(f"  ✓ Set action: {action.value}")
        else:
            typer.echo(f"  ✓ Action already set: {original_intent.action}")

        if not original_intent.subject:
            subject = fuzzy_select(
                "Who or what is this for or about?",
                nicer([x for x in ws.plans.get_subjects(date)]),
                escapable=True
            )
            if subject:
                updated_fields['subject'] = subject.value
                typer.echo(f"  ✓ Set subject: {subject.value}")
        else:
            typer.echo(f"  ✓ Subject already set: {original_intent.subject}")

        # Check if any fields were actually updated
        if not updated_fields:
            typer.echo("\nNo fields were updated.")
            return

        # Create updated intent with new fields
        updated_intent = Intent(
            alias=original_intent.alias,
            role=updated_fields.get('role', original_intent.role),
            objective=updated_fields.get('objective', original_intent.objective),
            action=updated_fields.get('action', original_intent.action),
            subject=updated_fields.get('subject', original_intent.subject),
            trackers=original_intent.trackers
        )

        # Ask about retroactive updates
        typer.echo("\n" + "="*60)
        logs_with_intent = ws.logs.find_logs_with_intent(original_intent.intent_id)

        if logs_with_intent:
            typer.echo(f"This intent is used in {len(logs_with_intent)} log file(s).")
            typer.echo("Would you like to update past sessions with the new field values?")
            typer.echo("")
            apply_retroactive = typer.confirm("Apply changes retroactively?", default=True)
        else:
            typer.echo("This intent hasn't been used in any sessions yet.")
            apply_retroactive = False

        # Update the plan file
        typer.echo("\nUpdating plan...")
        ws.plans.update_intent_by_id(original_intent.intent_id, updated_intent)
        typer.echo(f"✓ Updated intent in {Path(plan_file_path).name}")

        # Apply retroactive updates if requested
        if apply_retroactive:
            typer.echo("\nUpdating log files...")
            trackers = ws.plans.get_trackers(ws.today())
            total_updated = ws.logs.update_intent_in_logs(
                original_intent.intent_id,
                updated_intent,
                trackers
            )
            typer.echo(f"\n✓ Updated {total_updated} session(s) in {len(logs_with_intent)} log file(s)")

        typer.echo("\nIntent completed successfully!")

    except Exception as e:
        typer.echo(f"Error completing intent: {e}", err=True)
        raise typer.Exit(1)

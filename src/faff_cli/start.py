import typer
from typing import Sequence, List

from titlecase import titlecase


from faff_cli.ui import FuzzyItem, fuzzy_select

from faff_core import Workspace

from faff_core.models import Intent

app = typer.Typer(help="Start a new task or activity.")


def prettify_path_label(path: str) -> str:
    namespace = path.split(":")[0]
    path = path[len(namespace) + 1:] if namespace else path
    parts = path.strip("/").split("/")
    if not parts:
        return ""

    *prefix, raw_name = parts
    name = raw_name.replace("-", " ")
    name = titlecase(name)
    context = "/".join(prefix)

    return f"{name} ({namespace}:{path})" if context else name


def nicer(strings: Sequence[str]) -> list[str | FuzzyItem]:
    return [
        FuzzyItem(name=prettify_path_label(s), value=s, decoration=s)
        for s in strings
    ]

def nicer_tracker(strings: Sequence[str], ws: Workspace) -> list[str | FuzzyItem]:
    trackers = ws.plans.get_trackers(ws.today())
    return [
        FuzzyItem(name=trackers.get(s, ''), value=s, decoration=s)
        for s in strings
    ]

def print_sentence(role=None, action=None, objective=None, subject=None):
    """Print the intent sentence with filled/unfilled parts."""
    role_str = f"[bold cyan]{prettify_path_label(role)}[/bold cyan]" if role else "[dim]________[/dim]"
    action_str = f"[bold cyan]{prettify_path_label(action)}[/bold cyan]" if action else "[dim]________[/dim]"
    objective_str = f"[bold cyan]{prettify_path_label(objective)}[/bold cyan]" if objective else "[dim]________[/dim]"
    subject_str = f"[bold cyan]{prettify_path_label(subject)}[/bold cyan]" if subject else "[dim]________[/dim]"

    from rich.console import Console
    console = Console()

    sentence = f"  [dim]→[/dim] As a {role_str}, I am {action_str} to achieve {objective_str}, focused on {subject_str}."
    console.print(f"\n{sentence}\n")

def input_new_intent(alias: str, ws: Workspace) -> Intent:
    """
    Prompt the user for details to create a new intent.
    """
    from rich.console import Console
    console = Console()
    date = ws.today()

    console.print()
    console.print("[bold green]✓[/bold green] Great! Now, let's capture the details.", style="bold")
    console.print("[dim]Complete this sentence to describe what you're doing:[/dim]")
    print_sentence()

    console.print("[bold]What role are you performing here?[/bold]")
    console.print("[dim]e.g. Line Manager, Pre-Sales Engineer, Parent[/dim]")
    role, _ = fuzzy_select(
        "Role:",
        nicer([x for x in ws.plans.get_roles(date)]),
        escapable=True
    )
    print_sentence(role=role.value if role else None)

    console.print("[bold]What action are you doing?[/bold]")
    console.print("[dim]e.g. Planning, Attending a Scheduled Meeting[/dim]")
    action, _ = fuzzy_select(
        "Action:",
         nicer([x for x in ws.plans.get_actions(date)]),
         escapable=True
    )
    print_sentence(role=role.value if role else None, action=action.value if action else None)

    console.print("[bold]What outcome are you aiming for?[/bold]")
    console.print("[dim]e.g. Career Development, New Revenue New Business[/dim]")
    objective, _ = fuzzy_select(
        "Outcome:",
        nicer([x for x in ws.plans.get_objectives(date)]),
        escapable=True
    )
    print_sentence(role=role.value if role else None, action=action.value if action else None, objective=objective.value if objective else None)

    console.print("[bold]Who or what are you focused on here?[/bold]")
    console.print("[dim]e.g. John Smith, ACME Corporation, Sales Department[/dim]")
    subject, _ = fuzzy_select(
        "Focus:",
        nicer([x for x in ws.plans.get_subjects(date)]),
        escapable=True
    )
    print_sentence(role=role.value if role else None, action=action.value if action else None, objective=objective.value if objective else None, subject=subject.value if subject else None)

    trackers: List[str] = []
    all_trackers = list(ws.plans.get_trackers(date))

    # Only show tracker selection if there are trackers available
    if all_trackers:
        ingesting_trackers = True

        console.print("[bold]Add remote trackers?[/bold]")
        console.print("[dim]Select trackers or press Enter on empty line to finish.[/dim]")

        while ingesting_trackers:
            remaining = [x for x in all_trackers if x not in trackers]
            if not remaining:
                break

            # Add a "Done" option at the top
            choices = [FuzzyItem(name="[Done]", value=None, decoration="")] + nicer_tracker(remaining, ws)

            tracker_id, _ = fuzzy_select(
                prompt="Tracker:",
                choices=choices,
                escapable=True,
                create_new=False
            )
            if tracker_id and tracker_id.value:
                trackers.append(tracker_id.value)
            else:
                ingesting_trackers = False

    local_plan = ws.plans.get_local_plan_or_create(date)

    new_intent = Intent(
        alias=alias,
        role=role.value if role else None,
        objective=objective.value if objective else None,
        action=action.value if action else None,
        subject=subject.value if subject else None,
        trackers=trackers
    )

    new_plan = local_plan.add_intent(new_intent)
    ws.plans.write_plan(new_plan)

    # Get the intent back from the plan - it now has a generated ID
    intent_with_id = [i for i in new_plan.intents if i.alias == alias][-1]

    # Show final success message with complete intent
    console.print()
    console.print("[bold green]✓[/bold green] Intent created!", style="bold")
    print_sentence(role=role.value if role else None, action=action.value if action else None, objective=objective.value if objective else None, subject=subject.value if subject else None)

    return intent_with_id   

@app.callback(invoke_without_command=True)
def start(
    ctx: typer.Context,
    since: str = typer.Option(None, "--since", help="Start time (e.g., '14:30', 'now')"),
    continue_from_last: bool = typer.Option(False, "--continue", "-c", help="Start at the end of the previous session"),
):
    """Start a new task or activity."""
    try:
        ws: Workspace = ctx.obj
        date = ws.today()

        # Determine start time
        if continue_from_last:
            # Get the last session's end time
            log = ws.logs.get_log(date)
            if not log.timeline:
                typer.echo("No previous session found to continue from", err=True)
                raise typer.Exit(1)

            last_session = log.timeline[-1]
            if last_session.end is None:
                typer.echo("Previous session is still active", err=True)
                raise typer.Exit(1)

            start_time = last_session.end
        elif since:
            # Parse the provided time (restricted to today)
            start_time = ws.parse_natural_datetime(since)
        else:
            # Capture current time NOW, before any prompts
            start_time = ws.now()

        existing_intents = ws.plans.get_intents(date)

        from rich.console import Console
        console = Console()
        console.print()
        console.print("[bold]What are you doing?[/bold]")
        console.print("[dim]What would you call this activity if you were naming an entry in your calendar?[/dim]")
        console.print()

        chosen_intent, _ = fuzzy_select(
            prompt="Activity:",
            choices=intents_to_choices(existing_intents),
            escapable=False,
            slugify_new=False,
            )

        # If the intent is new, we'll want to prompt for details.
        if not chosen_intent:
            typer.echo("aborting")
            return
        if chosen_intent.is_new:
            intent = input_new_intent(chosen_intent.value, ws)
        else:
            intent = chosen_intent.value
        note = input("? Note for this session (optional): ")

        # Rust core handles validation (future time, overlaps) and auto-stops active session
        ws.logs.start_intent(intent, start_time, note if note else None)
        typer.echo(f"Started '{intent.alias}' at {start_time.strftime('%H:%M:%S')}")
    except Exception as e:
        typer.echo(f"Error starting session: {e}", err=True)
        raise typer.Exit(1)

def intents_to_choices(intents):
    """
    Convert intents to fuzzy select choices.
    If multiple intents share the same alias, disambiguate by adding the intent_id.
    """
    # Count alias occurrences to detect duplicates
    alias_counts = {}
    for intent in intents:
        alias_counts[intent.alias] = alias_counts.get(intent.alias, 0) + 1

    choices = []
    for intent in intents:
        # If this alias appears more than once, disambiguate with intent_id
        if alias_counts[intent.alias] > 1:
            display_name = f"{intent.alias} ({intent.intent_id})"
        else:
            display_name = intent.alias

        choices.append({
            "name": display_name,
            "value": intent,
            "decoration": None
        })

    return choices

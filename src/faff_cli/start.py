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

def input_new_intent(alias: str, ws: Workspace) -> Intent:
    """
    Prompt the user for details to create a new intent.
    """
    date = ws.today()

    role = fuzzy_select(
        "What job role are you playing in this activity?",
        nicer([x for x in ws.plans.get_roles(date)]),
        escapable=True
    )
    objective = fuzzy_select(
        "What is the main goal of this activity?",
        nicer([x for x in ws.plans.get_objectives(date)]),
        escapable=True
    )
    action = fuzzy_select(
        "What action are you doing?",
         nicer([x for x in ws.plans.get_actions(date)]),
         escapable=True
)
    subject = fuzzy_select(
        "Who or what is this for or about?",
        nicer([x for x in ws.plans.get_subjects(date)]),
        escapable=True
    )

    trackers: List[str] = []
    ingesting_trackers = True

    while ingesting_trackers:
        tracker_id = fuzzy_select(
            prompt="Please add any third-party trackers to attach (esc to finish):",
            choices = nicer_tracker([x for x in ws.plans.get_trackers(date) if x not in trackers], ws)
        )
        if tracker_id:
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

        chosen_intent = fuzzy_select(
            prompt="What are you doing?",
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

        note = input("? Note (optional): ")

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

import typer
from typing import Sequence, List

from titlecase import titlecase


from faff_cli.ui import FuzzyItem, fuzzy_select

from faff.core import Workspace

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
        nicer([x for x in ws.plans.get_roles(date)])
    )
    objective = fuzzy_select(
        "What is the main goal of this activity?",
        nicer([x for x in ws.plans.get_objectives(date)])
    )
    action = fuzzy_select(
        "What action are you doing?",
         nicer([x for x in ws.plans.get_actions(date)])
)
    subject = fuzzy_select(
        "Who or what is this for or about?",
        nicer([x for x in ws.plans.get_subjects(date)])
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

    local_plan = ws.plans.local_plan(date)

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

    return new_intent   

@app.callback(invoke_without_command=True)
def start(ctx: typer.Context):
    ctx.obj = Workspace()

    ws = ctx.obj
    date = ws.today()

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
    elif not chosen_intent.is_new:
        intent = chosen_intent.value
    
    note = input("? Note (optional): ")
    typer.echo(ws.logs.start_intent_now(intent, None, note))

def intents_to_choices(intents):
    choices = []

    for intent in intents:
        choices.append({
            "name": intent.alias,
            "value": intent,
            "decoration": None
        })

    return choices

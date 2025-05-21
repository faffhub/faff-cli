import typer

from InquirerPy import inquirer

from faff_cli.ui import fuzzy_select

from faff.core import Workspace
from faff_cli.utils import resolve_natural_date

from faff.models import Intent

app = typer.Typer(help="Start a new task or activity.")

@app.callback(invoke_without_command=True)
def start(ctx: typer.Context):
    ctx.obj = Workspace()

    ws = ctx.obj
    date = ws.today()

    intents = ws.plans.get_intents(date)
    x = []

    def decorate_intent(intent):
        if intent.activity == "VARIABLE":
            return "[TEMPLATE] (activity: x, y, z...)"
        elif intent.beneficiary == "VARIABLE":
            return "[TEMPLATE] (for: x, y, z...)"

    for intent in intents:
        x.append({
            "name": intent.alias,
            "value": intent,
            "decoration": decorate_intent(intent)
        })

    def decorate_entity(entity):
        try:
            scope, thing = entity.rsplit("/", 1)
        except ValueError:
            scope, thing = None, entity
        
        return {
            "name": thing,
            "value": entity,
            "decoration": f"({scope})"
        }

    VARIABLE = {
        "name": "[VARIABLE]",
        "value": "VARIABLE",
        "decoration": "(will change each time you record this activity)"
    }

    def thingify(x):
        return {
            "name": x,
            "value": x,
            "decoration": None
        }

    buckets = ws.plans.get_buckets(ws.today())

    intent, new_intent = fuzzy_select(prompt="Intent:", choices=x, escapable=True)
    if new_intent or not intent:
        # No intent found, so we need to create a new one.
        activity, new = fuzzy_select("I am doing:", [decorate_entity(x) for x in ws.plans.get_activities(date)] + [VARIABLE])
        role, new = fuzzy_select("as:", [decorate_entity(x) for x in ws.plans.get_roles(date)])
        goal, new = fuzzy_select("to achieve:", [decorate_entity(x) for x in ws.plans.get_goals(date)])
        beneficiary, new = fuzzy_select("for:", [thingify(x) for x in ws.plans.get_beneficiaries(date)] + [VARIABLE])

        choices = [
            {
                "name": f"{a.name}",
                "value": a,
                "decoration": f"({ws.plans.get_plan_by_bucket_id(a.id, date).source})"
            }
            for a in buckets.values()
        ]
        bucket, _ = fuzzy_select(
            prompt="Tracked under (esc for none):",
            choices=choices,
            create_new=False,
            escapable=True
        )

        if new_intent:
            alias = intent
        else: 
            suggested_name = f"{role}: {activity[0].upper() + activity[1:]} to {goal} for {beneficiary}"
            alias, _ = fuzzy_select(
                prompt="Name (esc for none):",
                choices=[suggested_name],
                create_new=True,
                escapable=True
            )

        local_plan = ws.plans.local_plan(date)
            
        new_intent = Intent(
            alias=alias,
            role=role,
            activity=activity,
            goal=goal,
            beneficiary=beneficiary,
            bucket_id=bucket.id if bucket else None
        )

        new_plan = local_plan.add_intent(new_intent)
        ws.plans.write_plan(new_plan)

        note = input("? Note (optional): ")
        typer.echo(ws.logs.start_intent_now(new_intent, None, note))

    else:
        # intent = intent.value
        # We have an existing intent, so we can use that.
        activity = intent.activity
        if activity == "VARIABLE":
            activity, new = fuzzy_select("I am doing:", [decorate_entity(x) for x in ws.plans.get_activities(date)])
        role = intent.role
        goal = intent.goal
        beneficiary = intent.beneficiary
        if beneficiary == "VARIABLE":
            beneficiary, new = fuzzy_select("for:", [thingify(x) for x in ws.plans.get_beneficiaries(date)])
        alias = intent.alias
        bucket = buckets.get(intent.bucket_id)

        note = input("? Note (optional): ")

        complete_intent = Intent(
            alias=alias,
            role=role,
            activity=activity,
            goal=goal,
            beneficiary=beneficiary,
            bucket_id=bucket.id if bucket else None
        )

        typer.echo(ws.logs.start_intent_now(complete_intent, None, note))

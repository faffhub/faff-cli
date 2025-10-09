import typer

from typing import List, Optional, Tuple

from faff.core import Workspace
from faff_core.models import Intent

from faff_cli.utils import resolve_natural_date

from typing import Dict
import datetime

from rich.table import Table
from rich.console import Console

"""
┌──────────────────────────────────────────┬───────────┐
│ objective                                │ duration  │
├──────────────────────────────────────────┼───────────┤
│ element:new-revenue-new-business         │ 3h 17m    │
│ element:professional-development         │ 0h 37m    │
│ element:operational-issues               │ 0h 28m    │
└──────────────────────────────────────────┴───────────┘
"""
app = typer.Typer(help="Query log entries across multiple days.", invoke_without_command=True)

def format_duration(td: datetime.timedelta) -> str:
    total_minutes = int(td.total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)

def gather_data(ws: Workspace,
                from_date: Optional[datetime.date],
                to_date: Optional[datetime.date],
                filters: List['Filter']) -> Dict[Intent, datetime.timedelta]:

    # For each date in the range, get the log and filter entries
    # all_entries = []
    matching_intents: Dict[Intent, datetime.timedelta] = {}
    for log in ws.logs.list():
        if from_date and log.date < from_date:
            continue
        if to_date and log.date > to_date:
            continue

        for session in log.timeline:
            # If all filters match add to matches
            if all(filter.matches(session.intent) for filter in filters):
                if session.intent not in matching_intents:
                    matching_intents[session.intent] = session.duration
                else:
                    matching_intents[session.intent] += session.duration

    return matching_intents

@app.callback()
def query(
    ctx: typer.Context, 
    filter_strings: List[str] = typer.Argument(
        None,
        help="Filters in the form key=value, key~value, or key!=value (e.g. role=element:solutions-architect).",
    ),
    group: Optional[str] = typer.Option(
        None,
        "--group", "-g",
        help="Field to group by (e.g. date, role, objective, subject).",
    ),
    from_date: Optional[str] = typer.Option(
        None,
        "--from", "-f",
        help="Start date (inclusive), e.g. 2025-10-01.",
    ),
    to_date: Optional[str] = typer.Option(
        None,
        "--to", "-t",
        help="End date (inclusive), e.g. 2025-10-07.",
    ),
    since: Optional[str] = typer.Option(
        None,
        "--since",
        help="Shortcut for --from <date> with open end (mutually exclusive with --from).",
    ),
    until: Optional[str] = typer.Option(
        None,
        "--until",
        help="Shortcut for --to <date> with open start (mutually exclusive with --to).",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output results as JSON.",
    ),
    sum_only: bool = typer.Option(
        False,
        "--sum",
        help="Print only the total duration.",
    ),
): 
    ws = ctx.obj

    # Validate mutually exclusive options
    if from_date and since:
        typer.echo("Error: --from and --since are mutually exclusive.")
        raise typer.Exit(code=1)
    if to_date and until:
        typer.echo("Error: --to and --until are mutually exclusive.")
        raise typer.Exit(code=1)
    
    # Resolve date range
    if since:
        from_date = since
    if until:
        to_date = until

    resolved_from_date = resolve_natural_date(ws.today(), from_date) if from_date else None
    resolved_to_date = resolve_natural_date(ws.today(), to_date) if to_date else None

    filters = [Filter.from_string(f) for f in filter_strings] if filter_strings else []

    matching_intents = gather_data(ws, resolved_from_date, resolved_to_date, filters)

    # Display matches
    console = Console()
    table = Table()
    for filter in filters:
        table.add_column(filter.key.capitalize())
    table.add_column("Duration", justify="right")

    summed_rows: Dict[Tuple, datetime.timedelta] = {}
    for intent in matching_intents:
        row = []
        for filter in filters:
            row.append(getattr(intent, filter.key) or "")

        t_row = tuple(row)
        if t_row in summed_rows:
            summed_rows[t_row] += matching_intents[intent]
        else:
            summed_rows[t_row] = matching_intents[intent]

    summed_rows = dict(sorted(summed_rows.items(), key=lambda item: item[1], reverse=True))

    for summed_row in summed_rows:
        table.add_row(*summed_row, format_duration(summed_rows[summed_row]))

    table.add_section()
    total_duration = sum(summed_rows.values(), datetime.timedelta())
    table.add_row("TOTAL", *["" for _ in range(len(filters) - 1)], format_duration(total_duration))

    console.print(table)


class Filter:
    def __init__(self, key: str, operator: str, value: str):
        if operator not in ['=', '~', '!=']:
            raise ValueError(f"Invalid operator: {operator}")
        if key not in ['alias', 'role', 'objective', 'action', 'subject']:
            raise ValueError(f"Invalid key: {key}")
        self.key = key
        self.operator = operator
        self.value = value
        
    @classmethod
    def from_string(cls, filter_str: str) -> 'Filter':
        if '=' in filter_str:
            key, value = filter_str.split('=', 1)
            return cls(key, '=', value)
        elif '~' in filter_str:
            key, value = filter_str.split('~', 1)
            return cls(key, '~', value)
        elif '!=' in filter_str:
            key, value = filter_str.split('!=', 1)
            return cls(key, '!=', value)
        else:
            raise ValueError(f"Invalid filter format: {filter_str}")

    def matches(self, intent: Intent) -> bool:
        intent_value = getattr(intent, self.key, None)
        if intent_value is None:
            return False

        if self.operator == '=':
            return intent_value == self.value
        elif self.operator == '~':
            return self.value in intent_value
        elif self.operator == '!=':
            return intent_value != self.value
        else:
            return False
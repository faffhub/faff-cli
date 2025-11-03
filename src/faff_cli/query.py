import typer

from typing import List, Optional

from faff_core import Workspace, Filter, query_sessions

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
                filters: List[Filter]) -> dict:
    """
    Query sessions using Rust query_sessions function.

    Returns a dict where keys are tuples of filter values and values are timedeltas.
    """
    # Get all logs
    logs = ws.logs.list_logs()

    # Call Rust query_sessions - it returns dict with tuple keys and i64 values (seconds)
    results = query_sessions(logs, filters, from_date, to_date)

    # Convert seconds back to timedelta for Python
    return {
        key: datetime.timedelta(seconds=duration_seconds)
        for key, duration_seconds in results.items()
    }

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

    resolved_from_date = ws.parse_natural_date(from_date) if from_date else None
    resolved_to_date = ws.parse_natural_date(to_date) if to_date else None

    filters = [Filter.parse(f) for f in filter_strings] if filter_strings else []

    summed_rows = gather_data(ws, resolved_from_date, resolved_to_date, filters)

    # Display matches
    console = Console()
    table = Table()
    for filter in filters:
        table.add_column(filter.field().capitalize())
    table.add_column("Duration", justify="right")

    summed_rows = dict(sorted(summed_rows.items(), key=lambda item: item[1], reverse=True))

    for summed_row in summed_rows:
        table.add_row(*summed_row, format_duration(summed_rows[summed_row]))

    table.add_section()
    total_duration = sum(summed_rows.values(), datetime.timedelta())
    table.add_row("TOTAL", *["" for _ in range(len(filters) - 1)], format_duration(total_duration))

    console.print(table)
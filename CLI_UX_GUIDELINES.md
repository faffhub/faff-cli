# Faff CLI User Experience Guidelines

**Version**: 1.0
**Date**: 2025-01-05
**Purpose**: Define the gold standard for all CLI interactions

---

## Design Principles

1. **Consistency Above All** - Users should predict behavior from past experience
2. **Progressive Disclosure** - Simple by default, powerful when needed
3. **Machine-Readable** - Every output should have a `--json` mode
4. **Filter Everything** - All list commands support filtering
5. **Clear Feedback** - Always confirm what happened
6. **Fail Safely** - Confirm destructive operations

---

## Output Formatting Standard

### Rule: Three Output Modes for All Commands

Every command that displays data MUST support:

```bash
faff <command>              # Default: Rich formatted (human-readable)
faff <command> --json       # Machine-readable JSON
faff <command> --plain      # Plain text (no colors, for piping)
```

### Default Output: Rich Formatting

**Use Rich tables for:**
- List commands with structured data
- Query results with multiple columns
- Comparison views

**Use Rich markup for:**
- Status displays with visual hierarchy
- Multi-line item descriptions
- Commands showing detailed object info

**Format Rules:**
```python
from rich.console import Console
from rich.table import Table

console = Console()

# Tables for structured data
table = Table(title="Optional Title")
table.add_column("Column", style="cyan")
table.add_column("Duration", justify="right")
table.add_row("value", "formatted")
console.print(table)

# Markup for hierarchical/detailed output
console.print(f"[bold cyan]{heading}[/bold cyan]")
console.print(f"  [dim]{label}:[/dim] {value}")
```

### JSON Output Mode

**Rules:**
1. Use `--json` flag (not `--output json` or `-j`)
2. Output valid JSON to stdout (nothing else)
3. No progress messages or warnings in JSON mode
4. Use consistent key names (snake_case)
5. Include metadata (counts, totals) in top-level object

**Example:**
```bash
$ faff intent list --json
{
  "intents": [
    {
      "intent_id": "local:i-20251104-abc",
      "alias": "My Intent",
      "role": "engineer",
      "session_count": 5,
      "log_count": 3
    }
  ],
  "total": 1
}
```

### Plain Text Mode

**Rules:**
1. Use `--plain` flag
2. No ANSI colors or escape codes
3. Tab-separated for tabular data
4. One item per line for lists
5. Suitable for piping to `grep`, `awk`, etc.

---

## Filtering Standard

### Rule: Universal Filter Syntax

Based on `faff log query` (the gold standard), ALL list commands MUST support:

```bash
# Filter syntax
faff <command> list <field>=<value>      # Exact match
faff <command> list <field>~<value>      # Contains match (case-insensitive)
faff <command> list <field>!=<value>     # Not equal

# Multiple filters (AND logic)
faff <command> list role=engineer objective~revenue

# Date ranges (for time-based data)
faff <command> list --from 2025-01-01 --to 2025-01-31
faff <command> list --since 2025-01-01   # Shortcut: from date onwards
faff <command> list --until 2025-01-31   # Shortcut: up to date

# Grouping (where relevant)
faff <command> list --group <field>

# Limiting results
faff <command> list --limit 10
```

### Implementation Pattern

```python
from faff_core import Filter
from typing import List, Optional
import datetime

@app.command(name="list")
def list_items(
    ctx: typer.Context,
    filter_strings: List[str] = typer.Argument(
        None,
        help="Filters: field=value, field~value, field!=value",
    ),
    from_date: Optional[str] = typer.Option(None, "--from", "-f"),
    to_date: Optional[str] = typer.Option(None, "--to", "-t"),
    since: Optional[str] = typer.Option(None, "--since"),
    until: Optional[str] = typer.Option(None, "--until"),
    group: Optional[str] = typer.Option(None, "--group", "-g"),
    limit: Optional[int] = typer.Option(None, "--limit", "-n"),
    json_output: bool = typer.Option(False, "--json"),
    plain_output: bool = typer.Option(False, "--plain"),
):
    ws: Workspace = ctx.obj

    # Validate mutually exclusive options
    if from_date and since:
        typer.echo("Error: --from and --since are mutually exclusive.", err=True)
        raise typer.Exit(1)

    # Parse filters
    filters = [Filter.parse(f) for f in filter_strings] if filter_strings else []

    # Resolve dates
    resolved_from = ws.parse_natural_date(from_date or since) if (from_date or since) else None
    resolved_to = ws.parse_natural_date(to_date or until) if (to_date or until) else None

    # Query data through Rust layer
    results = query_data(ws, filters, resolved_from, resolved_to, group)

    # Apply limit
    if limit:
        results = results[:limit]

    # Output based on mode
    if json_output:
        output_json(results)
    elif plain_output:
        output_plain(results)
    else:
        output_rich(results)
```

---

## Sorting Standard

### Rule: Chronological Order for Time-Based Data

**Default sorting:**
- **Time-based data** (logs, timesheets, sessions): **Chronological order (oldest to newest)**
- **Usage-based data** (intents, fields): **Most used first (descending)**
- **Alphabetical data** (remotes, plugins): **Alphabetical (ascending)**

**Rationale for chronological order:**
- Users think of time narratively: "What happened from Monday onwards?"
- Reviewing work is a forward-looking process
- Most recent entry is shown by `faff status`, not list commands
- Date ranges (`--from`, `--to`) imply forward chronology

**Examples:**
```bash
# Logs: oldest to newest (chronological)
faff log list
# 2025-01-01
# 2025-01-02
# 2025-01-03

# Intents: most used first (relevance)
faff intent list
# (100 sessions) Daily Standup
# (50 sessions)  Code Review
# (5 sessions)   One-off Task

# Remotes: alphabetical
faff remote list
# alpha
# beta
# gamma
```

**Implementation:**
```python
# For time-based data
items.sort(key=lambda x: x["date"], reverse=False)  # Chronological

# For usage-based data
items.sort(key=lambda x: x["session_count"], reverse=True)  # Most used first

# For alphabetical data
items.sort(key=lambda x: x["name"], reverse=False)  # A-Z
```

---

## Date Handling Standard

### Rule: Consistent Date Arguments and Natural Language

**For single-date commands:**
```bash
faff <command> [date]                    # Optional positional, defaults to today
faff log edit                            # Today
faff log edit yesterday                  # Natural language
faff log edit 2025-01-05                 # ISO format
```

**For date-range commands:**
```bash
faff <command> --from <date> --to <date>
faff <command> --since <date>            # From date onwards (open end)
faff <command> --until <date>            # Up to date (open start)
```

**Implementation:**
```python
# Single date
date: str = typer.Argument(None, help="Date (defaults to today, supports natural language)")
resolved_date = ws.parse_natural_date(date)

# Date range
from_date: Optional[str] = typer.Option(None, "--from", "-f", help="Start date (inclusive)")
to_date: Optional[str] = typer.Option(None, "--to", "-t", help="End date (inclusive)")
```

---

## Success Messages Standard

### Rule: Checkmark Prefix + Past Tense + Specifics

**Format:** `✓ <Past tense action> <specific details>.`

**Examples:**
```
✓ Installed plugin 'myhours'.
✓ Updated 15 session(s) across 3 log file(s).
✓ Compiled and signed timesheet for 2025-01-05.
✓ Created derived intent 'local:i-20251105-xyz'.
```

**Implementation:**
```python
typer.echo(f"✓ {action} {details}.")
```

**DO NOT:**
- Mix with/without checkmark: ❌ "Configuration file was updated"
- Use present tense: ❌ "Installing plugin"
- Be vague: ❌ "Success"
- Omit period: ❌ "✓ Done"

---

## Error Messages Standard

### Rule: Clear Problem + Suggestion

**Format:** `Error: <what went wrong>. <how to fix it>`

**Examples:**
```
Error: Intent with ID 'foo' not found. Use 'faff intent list' to see available intents.
Error: --from and --since are mutually exclusive.
Error: No log found for 2025-01-05. Create one with 'faff start'.
```

**Implementation:**
```python
try:
    # operation
except SpecificError as e:
    typer.echo(f"Error: {specific_problem}. {suggestion}", err=True)
    raise typer.Exit(1)
```

**For warnings (non-fatal):**
```python
typer.echo(f"⚠️  {warning_message}", err=True)
```

---

## Confirmation Prompts Standard

### Rule: Confirm Destructive Operations with Summary

**When to confirm:**
- Deleting data
- Modifying multiple files
- Operations that can't be undone

**Pattern:**
```python
# Show summary
typer.echo("="*60)
typer.echo("OPERATION SUMMARY")
typer.echo("="*60)
typer.echo(f"Will modify: {count} files")
typer.echo(f"Items affected:")
for item in items[:5]:
    typer.echo(f"  - {item}")
if len(items) > 5:
    typer.echo(f"  ... and {len(items) - 5} more")
typer.echo("="*60)

if not typer.confirm("Proceed?", default=False):
    typer.echo("Cancelled.")
    return
```

**Allow skipping for automation:**
```python
yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation")

if not yes:
    if not typer.confirm("Proceed?"):
        typer.echo("Cancelled.")
        return
```

---

## Help Text Standard

### Rule: Concise Description + Examples

**Command docstring pattern:**
```python
@app.command()
def command_name(ctx: typer.Context, arg: str):
    """
    <One-line summary of what the command does>.

    <Optional: More detailed explanation if needed.>
    <Optional: Specific behavior notes.>

    Examples:
        faff command example-arg
        faff command example-arg --option value
    """
```

**Argument help pattern:**
```python
arg: str = typer.Argument(
    ...,  # or None for optional
    help="<What this argument is> (e.g., 'intent-id', 'date')"
)

option: str = typer.Option(
    None,
    "--option", "-o",
    help="<What this does>. <Default behavior if not specified>."
)
```

---

## Command Naming Standard

### Rule: Verb + Noun, Consistent Across Subsystems

**Command structure:**
```
faff <subsystem> <action> [arguments] [options]
```

**Standard actions:**
- `list` - Show all items (with optional filtering)
- `show` - Show detailed view of one item
- `edit` - Open item in editor
- `add` / `create` - Create new item
- `remove` / `rm` / `delete` - Delete item
- `update` - Modify item programmatically

**Examples:**
```bash
faff log list                    # List all logs
faff log show [date]            # Show specific log
faff log edit [date]            # Edit specific log
faff log rm <date>              # Remove specific log

faff intent list [filters]       # List intents
faff intent show <id>           # Show intent details
faff intent edit <id>           # Edit intent
faff intent derive <id>         # Create derived intent
faff intent replace <old> <new> # Replace intent usage

faff remote list                 # List remotes
faff remote show <id>           # Show remote details
faff remote add <id> <plugin>   # Add new remote
faff remote edit <id>           # Edit remote config
```

**Top-level convenience commands are allowed:**
```bash
faff start                       # Shortcut for creating sessions
faff stop                        # Shortcut for stopping session
faff status                      # Overview across subsystems
faff pull                        # Pull from all remotes
faff compile                     # Compile timesheets
faff push                        # Submit timesheets
```

---

## Application to Each Command Type

### 1. List Commands (`faff <subsystem> list`)

**Standard signature:**
```python
@app.command(name="list")
def list_items(
    ctx: typer.Context,
    filter_strings: List[str] = typer.Argument(None, help="Filters: field=value, field~value, field!=value"),
    from_date: Optional[str] = typer.Option(None, "--from", "-f"),
    to_date: Optional[str] = typer.Option(None, "--to", "-t"),
    group: Optional[str] = typer.Option(None, "--group", "-g"),
    limit: Optional[int] = typer.Option(None, "--limit", "-n"),
    json_output: bool = typer.Option(False, "--json"),
    plain_output: bool = typer.Option(False, "--plain"),
):
    """
    List all <items> with optional filtering.

    Examples:
        faff <subsystem> list
        faff <subsystem> list field=value
        faff <subsystem> list field~partial --from 2025-01-01
    """
```

**Output rules:**
- Default: Rich table with key columns
- Include counts at bottom: `Total: X items`
- Sort by relevance (usage, date, alphabetical)
- Show metadata (dates, counts, status indicators)

**Examples:**

#### `faff log list`
```bash
# List all logs
$ faff log list

┌────────────┬──────┬──────────┬───────────┬────────┐
│ Date       │ Day  │ Duration │ Sessions  │ Status │
├────────────┼──────┼──────────┼───────────┼────────┤
│ 2025-01-05 │ SUN  │ 6h 23m   │ 8         │ ✓      │
│ 2025-01-04 │ SAT  │ 4h 12m   │ 5         │ ✓      │
│ 2025-01-03 │ FRI  │ 7h 45m   │ 12        │ ⚠      │
└────────────┴──────┴──────────┴───────────┴────────┘
Total: 3 logs

# With filters
$ faff log list --from 2025-01-01 --until 2025-01-31 --json

# With grouping
$ faff log list --group date --since 2025-01-01
```

#### `faff intent list`
```bash
# List all intents
$ faff intent list

local:i-20251104-abc  Customer Meeting  (15 sessions, 8 logs)  2025-11-04 →
  As consultant I do facilitate to achieve alignment for customer/acme

element:POC-29  POC Demo  (8 sessions, 5 logs)  2025-10-15 →
  As engineer I do demo to achieve new-revenue for poc/european-commission

Total: 42 intents

# With filters
$ faff intent list role=engineer objective~revenue --limit 10

# Machine-readable
$ faff intent list --json
```

#### `faff remote list`
```bash
# List all remotes
$ faff remote list

┌──────────┬─────────┬────────────┬────────────────┐
│ ID       │ Plugin  │ Last Pull  │ Active Plans   │
├──────────┼─────────┼────────────┼────────────────┤
│ element  │ myhours │ 2h ago     │ 1              │
│ personal │ static  │ never      │ 1              │
└──────────┴─────────┴────────────┴────────────────┘
Total: 2 remotes
```

#### `faff timesheet list`
```bash
# List all timesheets
$ faff timesheet list

┌──────────┬────────────┬─────────────┬─────────────┬──────────┐
│ Audience │ Date       │ Compiled    │ Submitted   │ Duration │
├──────────┼────────────┼─────────────┼─────────────┼──────────┤
│ element  │ 2025-01-05 │ 2h ago      │ 1h ago      │ 6h 23m   │
│ element  │ 2025-01-04 │ 1d ago      │ not sent    │ 4h 12m   │
└──────────┴────────────┴─────────────┴─────────────┴──────────┘
Total: 2 timesheets

# With filters
$ faff timesheet list submitted=false --from 2025-01-01
```

#### `faff plugin list`
```bash
# List installed plugins
$ faff plugin list

┌───────────────────┬──────────────────┬─────────────┐
│ Plugin            │ Instances        │ Status      │
├───────────────────┼──────────────────┼─────────────┤
│ faff-plugin-myhrs │ element, client  │ ✓           │
│ faff-plugin-jira  │ none             │ ⚠ no config │
└───────────────────┴──────────────────┴─────────────┘
Total: 2 plugins
```

---

### 2. Show Commands (`faff <subsystem> show`)

**Standard signature:**
```python
@app.command()
def show(
    ctx: typer.Context,
    identifier: str,
    json_output: bool = typer.Option(False, "--json"),
    plain_output: bool = typer.Option(False, "--plain"),
):
    """
    Show detailed information about a specific <item>.

    Examples:
        faff <subsystem> show <id>
        faff <subsystem> show <id> --json
    """
```

**Output rules:**
- Default: Rich formatted with hierarchical structure
- Include all details (not just summary)
- Show related items/usage
- Clear section headers

**Examples:**

#### `faff intent show <intent-id>`
```bash
$ faff intent show local:i-20251104-abc

[bold cyan]Intent: local:i-20251104-abc[/bold cyan]

[bold]Alias:[/bold] Customer Meeting
[bold]Valid From:[/bold] 2025-11-04 →

[bold]ROAST:[/bold]
  Role:      consultant
  Objective: alignment
  Action:    facilitate
  Subject:   customer/acme

[bold]Trackers:[/bold]
  - element:12345 (Customer X Support)

[bold]Usage:[/bold]
  15 sessions across 8 logs
  First used: 2025-11-04
  Last used:  2025-01-05

[bold]Source Plan:[/bold]
  local (2025-11-04.toml)
```

#### `faff log show <date>`
```bash
# This would be similar to current `faff log` but with structured output
$ faff log show 2025-01-05

[bold]Log for 2025-01-05 (Sunday)[/bold]

Total recorded: 6h 23m
Mean reflection score: 3.8/5
Sessions: 8 (all closed)

[Timeline details...]
```

---

### 3. Edit Commands (`faff <subsystem> edit`)

**Standard signature:**
```python
@app.command()
def edit(
    ctx: typer.Context,
    identifier: str,
    skip_validation: bool = typer.Option(False, "--force"),
):
    """
    Edit <item> in your preferred editor.

    Examples:
        faff <subsystem> edit <id>
    """
```

**Behavior:**
1. Validate item exists
2. Open in editor (using `edit_file()` utility)
3. Detect changes
4. If changed, show summary and confirm
5. Apply changes
6. Success message

**Example:**
```bash
$ faff log edit 2025-01-05
# Opens editor
# After saving:

Changes detected:
  - Added 1 session
  - Modified 2 sessions

Apply changes? [y/N]: y
✓ Updated log for 2025-01-05.
```

---

### 4. Query Commands (`faff <subsystem> query`)

**Standard signature:**
```python
@app.command()
def query(
    ctx: typer.Context,
    filter_strings: List[str] = typer.Argument(None),
    from_date: Optional[str] = typer.Option(None, "--from", "-f"),
    to_date: Optional[str] = typer.Option(None, "--to", "-t"),
    group: Optional[str] = typer.Option(None, "--group", "-g"),
    limit: Optional[int] = typer.Option(None, "--limit", "-n"),
    sum_only: bool = typer.Option(False, "--sum"),
    json_output: bool = typer.Option(False, "--json"),
):
    """
    Query <items> with aggregation and grouping.

    Examples:
        faff <subsystem> query field=value --group field
        faff <subsystem> query --from 2025-01-01 --group date
    """
```

**Output rules:**
- Show aggregated results (usually durations/counts)
- Always include totals
- Sort by aggregate value (descending)
- Support `--sum` for just total

**Example (existing gold standard):**
```bash
$ faff log query objective~revenue --from 2025-01-01 --group objective

┌──────────────────────────────────┬──────────┐
│ Objective                        │ Duration │
├──────────────────────────────────┼──────────┤
│ element:new-revenue-new-business │ 23h 15m  │
│ element:new-revenue-existing     │ 8h 45m   │
├──────────────────────────────────┼──────────┤
│ TOTAL                            │ 32h 0m   │
└──────────────────────────────────┴──────────┘
```

---

### 5. Create/Add Commands

**Standard signature:**
```python
@app.command()
def add(
    ctx: typer.Context,
    name: str,
    # ... required fields
    option: Optional[str] = typer.Option(None, "--option"),
):
    """
    Create a new <item>.

    Examples:
        faff <subsystem> add <name>
        faff <subsystem> add <name> --option value
    """
```

**Behavior:**
1. Validate inputs
2. Check for conflicts (existing items)
3. Create item
4. Success message with next steps

**Example:**
```bash
$ faff remote add myclient faff-plugin-myhours
✓ Created remote 'myclient' from plugin template.

Next steps:
  1. Edit configuration: faff remote edit myclient
  2. Pull plans: faff pull myclient
```

---

### 6. Remove/Delete Commands

**Standard signature:**
```python
@app.command()
def rm(
    ctx: typer.Context,
    identifier: str,
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """
    Remove a <item>.

    Examples:
        faff <subsystem> rm <id>
        faff <subsystem> rm <id> --yes
    """
```

**Behavior:**
1. Check if item exists
2. Show summary of what will be deleted
3. Show impact (what else uses this)
4. Confirm (unless `--yes`)
5. Delete
6. Success message

**Example:**
```bash
$ faff log rm 2025-01-05

Log for 2025-01-05 contains:
  - 8 sessions
  - 6h 23m recorded time
  - 5 sessions with reflections

Delete this log? [y/N]: y
✓ Removed log for 2025-01-05.
```

---

### 7. Update/Modify Commands

**Standard signature:**
```python
@app.command()
def update(
    ctx: typer.Context,
    identifier: str,
    field: str,
    value: str,
    yes: bool = typer.Option(False, "--yes", "-y"),
):
    """
    Update a field on <item>.

    Examples:
        faff <subsystem> update <id> <field> <value>
    """
```

**Behavior:**
1. Validate item exists
2. Show before/after
3. Show impact (how many other items affected)
4. Confirm
5. Apply changes
6. Success message with counts

**Example:**
```bash
$ faff field replace role old-engineer new-engineer

═══════════════════════════════════════════════════
FIELD REPLACEMENT SUMMARY
═══════════════════════════════════════════════════
Field:     role
Old value: old-engineer
New value: new-engineer

Will update:
  - 15 intents across 3 plan files
  - 87 sessions across 23 log files
═══════════════════════════════════════════════════

Proceed? [y/N]: y

✓ Updated 15 intent(s) across 3 plan(s).
✓ Updated 87 session(s) across 23 log(s).
```

---

### 8. Interactive Commands

**Examples:** `faff start`, `faff reflect`

**Rules:**
1. Use fuzzy select for choices (via `fuzzy_select()`)
2. Clear prompts with context
3. Show current state before prompting
4. Allow escape/cancel
5. Success message when complete

**Example (existing):**
```bash
$ faff start
? What are you doing?
  > Customer Meeting
    POC Demo
    Code Review
    [Type to filter or create new...]

? Note (optional): Discussed Q1 roadmap

✓ Started session: Customer Meeting
Working on Customer Meeting for 0 seconds
```

---

## Migration Strategy

### Phase 1: Core Infrastructure
1. Create unified output formatter module (`faff_cli/output.py`)
   - `format_rich(data)`, `format_json(data)`, `format_plain(data)`
2. Create unified filtering module (`faff_cli/filtering.py`)
   - Shared filter parsing, date resolution, validation
3. Add tests for both

### Phase 2: Refactor by Subsystem
1. **Start with `log` commands** (already has `query` as gold standard)
   - `log list` - add filtering, date ranges, output modes
   - `log show` - create new command for detailed view
   - `log edit` - validate against standard
2. **Then `intent` commands** (partially there)
   - `intent list` - add JSON output, standardize filters
   - `intent show` - create new command
   - `intent edit/derive/replace` - validate confirmations
3. **Then `timesheet`, `remote`, `plan`, `field`**
4. **Finally `plugin`**

### Phase 3: Documentation
1. Update all help text to match standards
2. Create examples document
3. Add tests for all commands

### Phase 4: Top-level Consolidation
1. Remove duplicate `compile`/`push` from timesheet.py
2. Clarify `pull` vs `plan remotes` vs `remote list`
3. Document top-level convenience commands

---

## Checklist for New Commands

When adding a new command, ensure:

- [ ] Follows naming convention (verb + noun)
- [ ] Has comprehensive docstring with examples
- [ ] Supports `--json` and `--plain` output modes
- [ ] Uses Rich formatting for default output
- [ ] Implements filtering if it's a list/query command
- [ ] Uses `ws.parse_natural_date()` for date arguments
- [ ] Confirms destructive operations with summary
- [ ] Success messages use `✓ <action>` format
- [ ] Error messages include suggestions
- [ ] All options have clear help text
- [ ] Validates mutually exclusive options
- [ ] Exits with code 1 on error
- [ ] Uses `typer.echo(..., err=True)` for errors

---

## Testing Standard

Every command should have tests for:

1. **Happy path** - Normal successful execution
2. **Edge cases** - Empty results, single result, many results
3. **Error handling** - Invalid inputs, missing data
4. **Output modes** - JSON, plain, rich all work correctly
5. **Filtering** - All filter operators work
6. **Date handling** - Natural language, ranges, defaults

---

**End of Guidelines**

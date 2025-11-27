"""
SQL querying for faff ledger.

Commands:
faff sql
faff sql <query>
"""

import sqlite3
import sys
import os
import tempfile
import subprocess
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console

app = typer.Typer(help="Query your faff ledger using SQL")

def load_ledger_to_db(ws, db_path: Path):
    """Load the entire faff ledger into a SQLite database file."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create sessions table
    cursor.execute('''
        CREATE TABLE sessions (
            date TEXT,
            intent_id TEXT,
            alias TEXT,
            role TEXT,
            objective TEXT,
            action TEXT,
            subject TEXT,
            start TEXT,
            end TEXT,
            duration_minutes INTEGER,
            note TEXT,
            reflection TEXT,
            reflection_score INTEGER
        )
    ''')

    # Load all logs
    logs = ws.logs.list_logs()

    for log in logs:
        date_str = log.date.isoformat()

        for session in log.timeline:
            intent = session.intent

            # Calculate duration in minutes
            duration = None
            if session.end:
                duration = int((session.end - session.start).total_seconds() / 60)

            # Insert session
            cursor.execute('''
                INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                date_str,
                intent.intent_id,
                intent.alias,
                intent.role,
                intent.objective,
                intent.action,
                intent.subject,
                session.start.isoformat(),
                session.end.isoformat() if session.end else None,
                duration,
                session.note,
                session.reflection,
                session.reflection_score
            ))

    # Create useful indexes
    cursor.execute('CREATE INDEX idx_sessions_date ON sessions(date)')
    cursor.execute('CREATE INDEX idx_sessions_role ON sessions(role)')
    cursor.execute('CREATE INDEX idx_sessions_intent ON sessions(intent_id)')

    conn.commit()
    conn.close()


@app.callback(invoke_without_command=True)
def sql_callback(
    ctx: typer.Context,
    query_str: Optional[str] = typer.Argument(None, help="SQL query to execute"),
):
    """
    Query your faff ledger using SQL.

    If no query is provided, starts an interactive sqlite3 shell.
    If a query is provided via argument or stdin, executes it and outputs results.

    Examples:
        faff sql "SELECT role, SUM(duration_seconds)/3600.0 as hours FROM sessions GROUP BY role"
        echo "SELECT * FROM sessions WHERE date = '2025-01-15'" | faff sql
        faff sql  # Interactive mode with full sqlite3 features
    """
    ws = ctx.obj
    console = Console()
    err_console = Console(stderr=True)

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        # Load ledger
        err_console.print("[dim]Loading ledger into SQL database...[/dim]")
        load_ledger_to_db(ws, db_path)
        err_console.print(f"[dim]Ready. Table: sessions[/dim]")

        # Check if query from stdin
        if query_str is None and not sys.stdin.isatty():
            query_str = sys.stdin.read().strip()

        if query_str:
            # Execute single query using sqlite3 CLI
            result = subprocess.run(
                ['sqlite3', str(db_path), query_str],
                capture_output=False,
                check=False
            )
            raise typer.Exit(result.returncode)
        else:
            # Interactive mode - just exec sqlite3
            os.execvp('sqlite3', ['sqlite3', str(db_path)])
    finally:
        # Only cleanup if we didn't exec (i.e., we ran a query)
        if db_path.exists():
            db_path.unlink()

import typer
from faff_core import Workspace
from faff_core.models import Log

app = typer.Typer(help="Reflect on work sessions.")


def get_sessions_without_reflection(log):
    """Return sessions that don't have any reflection data."""
    return [
        (i, session) for i, session in enumerate(log.timeline)
        if session.reflection_score is None and session.reflection is None
    ]


@app.callback(invoke_without_command=True)
def reflect(ctx: typer.Context, date: str = typer.Argument(None)):
    """
    Reflect on sessions for a given date (defaults to today).

    Walks through each session that doesn't have reflection data,
    prompting for a score (1-5) and freeform reflection text.
    """
    try:
        ws: Workspace = ctx.obj
        resolved_date = ws.parse_natural_date(date)

        # Get the log for the specified date
        if not ws.logs.log_exists(resolved_date):
            typer.echo(f"No log found for {resolved_date}.")
            raise typer.Exit(1)

        log = ws.logs.get_log(resolved_date)

        # Filter to sessions without reflections
        sessions_to_reflect = get_sessions_without_reflection(log)

        if not sessions_to_reflect:
            typer.echo(f"All sessions for {resolved_date} already have reflections.")
            return

        typer.echo(f"Reflecting on {len(sessions_to_reflect)} session(s) for {resolved_date}:")
        typer.echo()

        # Walk through each session
        for session_idx, session in sessions_to_reflect:
            # Display session info
            start_time = session.start.strftime("%H:%M")
            end_time = session.end.strftime("%H:%M") if session.end else "ongoing"
            typer.echo(f"Session {session_idx + 1}/{len(log.timeline)}")
            typer.echo(f"  Time: {start_time} - {end_time}")
            typer.echo(f"  Intent: {session.intent.alias}")
            if session.note:
                typer.echo(f"  Note: {session.note}")
            typer.echo()

            # Prompt for score (1-5)
            while True:
                score_input = typer.prompt("  Score (1-5, or 'skip' to skip this session)")
                if score_input.lower() == 'skip':
                    typer.echo("  Skipped.")
                    typer.echo()
                    break

                try:
                    score = int(score_input)
                    if 1 <= score <= 5:
                        # Prompt for reflection text
                        reflection_text = typer.prompt("  Reflection (optional, press Enter to skip)", default="")

                        # Create updated session with reflection
                        updated_session = session.with_reflection(
                            score,
                            reflection_text if reflection_text else None
                        )

                        # Create new timeline with updated session
                        new_timeline = [
                            updated_session if i == session_idx else s
                            for i, s in enumerate(log.timeline)
                        ]

                        # Create new log with updated timeline
                        log = Log(
                            date=log.date,
                            timezone=log.timezone,
                            timeline=new_timeline
                        )

                        typer.echo()
                        break
                    else:
                        typer.echo("  Please enter a number between 1 and 5.")
                except ValueError:
                    typer.echo("  Please enter a valid number or 'skip'.")

        # Write the updated log
        trackers = ws.plans.get_trackers(resolved_date)
        ws.logs.write_log(log, trackers)

        typer.echo("Reflections saved.")

    except Exception as e:
        typer.echo(f"Error reflecting on sessions: {e}", err=True)
        raise typer.Exit(1)

import typer

from faff_cli import log, id, plan, start, timesheet, intent, field, remote, plugin, reflect, session, sql, __version__
from faff_cli.utils import edit_file

import faff_core
from faff_core import Workspace, FileSystemStorage
from faff_core.plugins import PlanSource

cli = typer.Typer()

# Track your Time
cli.add_typer(start.app, name="start", rich_help_panel="Track your Time")
cli.add_typer(session.app, name="session", rich_help_panel="Track your Time")
cli.add_typer(reflect.app, name="reflect", rich_help_panel="Track your Time")

# Compile and Submit Timesheets
cli.add_typer(timesheet.app, name="timesheet", rich_help_panel="Compile and Submit Timesheets")

# Maintain Plans and Intents
cli.add_typer(plan.app, name="plan", rich_help_panel="Maintain Plans and Intents")
cli.add_typer(intent.app, name="intent", rich_help_panel="Maintain Plans and Intents")
cli.add_typer(field.app, name="field", rich_help_panel="Maintain Plans and Intents")

# Ledger Setup
cli.add_typer(remote.app, name="remote", rich_help_panel="Ledger Setup")
cli.add_typer(id.app, name="id", rich_help_panel="Ledger Setup")
cli.add_typer(plugin.app, name="plugin", rich_help_panel="Ledger Setup")

@cli.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version and exit"),
):
    # Handle --version flag
    if version:
        typer.echo(f"faff-cli version: {__version__}")
        typer.echo(f"faff-core version: {faff_core.version()}")
        raise typer.Exit(0)

    # If no command provided, show help
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)

    # Don't create workspace for init command - it doesn't need one
    if ctx.invoked_subcommand == "init":
        ctx.obj = None
    else:
        ctx.obj = Workspace()

@cli.command(rich_help_panel="Ledger Setup")
def init(ctx: typer.Context):
    """
    Initialize a new faff ledger.

    Creates the directory structure and configuration needed for a faff ledger.

    By default, faff creates a hidden directory at ~/.faff. You can override this
    with the FAFF_DIR environment variable to use a custom location directly.

    Examples:
        faff init                                    # Creates ~/.faff/
        FAFF_DIR=~/Obsidian/vault faff init         # Creates ~/Obsidian/vault/ (no hidden folder)
        FAFF_DIR=~/ledger faff init                 # Creates ~/ledger/
    """
    # init doesn't need a workspace - ctx.obj will be None
    typer.echo("Initializing faff ledger...")
    try:
        storage = FileSystemStorage.init_at(None)
        typer.echo(f"✓ Initialized faff ledger at {storage.base_dir()}.")
    except Exception as e:
        typer.echo(f"Error: Failed to initialize faff ledger: {e}", err=True)
        raise typer.Exit(1)

@cli.command(rich_help_panel="Ledger Setup")
def config(ctx: typer.Context):
    """
    Edit ledger configuration.

    Opens the ledger's configuration file in your default editor.

    Examples:
        faff config
    """
    ws = ctx.obj
    from pathlib import Path
    if edit_file(Path(ws.storage().config_file())):
        typer.echo("✓ Configuration file was updated.")
    else:
        typer.echo("No changes detected.")

@cli.command(rich_help_panel="Track your Time")
def pull(
    ctx: typer.Context,
    remote_id: str = typer.Argument(None, help="Remote to pull from (omit for all)"),
):
    """
    Pull plans from remote sources.

    Downloads the latest plans from configured remotes. Omit the remote name to
    pull from all configured remotes.

    Examples:
        faff pull
        faff pull element
        faff pull mycompany
    """
    try:
        ws: Workspace = ctx.obj
        remotes = ws.plans.remotes()

        if remote_id:
            remotes = [r for r in remotes if r.id == remote_id]
            if len(remotes) == 0:
                typer.echo(f"Unknown remote: {remote_id}", err=True)
                raise typer.Exit(1)

        for remote_plugin in remotes:
            # Only pull from plan sources, not audiences
            if not isinstance(remote_plugin, PlanSource):
                continue

            try:
                plan = remote_plugin.pull_plan(ws.today())
                if plan:
                    ws.plans.write_plan(plan)
                    typer.echo(f"Pulled plan from {remote_plugin.id}")
                else:
                    typer.echo(f"No plans found for {remote_plugin.id}")
            except Exception as e:
                typer.echo(f"Error pulling plan from {remote_plugin.id}: {e}", err=True)
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error pulling plans: {e}", err=True)
        raise typer.Exit(1)


@cli.command(rich_help_panel="Compile and Submit Timesheets")
def compile(
    ctx: typer.Context,
    date: str = typer.Argument(None, help="Specific date to compile (omit for all uncompiled)"),
    audience: str = typer.Option(None, "--audience", "-a", help="Specific audience (omit for all)"),
):
    """
    Compile timesheets from logs.

    Compiles time logs into timesheets for configured audiences. By default,
    compiles all logs that don't have timesheets yet. Specify a date to force
    recompile.

    Examples:
        faff compile
        faff compile 2025-01-15
        faff compile --audience element
        faff compile yesterday --audience mycompany
    """
    try:
        ws = ctx.obj
        audiences = ws.timesheets.audiences()

        if audience:
            audiences = [a for a in audiences if a.id == audience]
            if len(audiences) == 0:
                typer.echo(f"Unknown audience: {audience}", err=True)
                raise typer.Exit(1)

        if date:
            # Specific date provided - compile that date
            resolved_date = ws.parse_natural_date(date)
            log = ws.logs.get_log(resolved_date)

            # FIXME: This check should be in faff-core, not faff-cli
            # The compile_time_sheet method should refuse to compile logs with active sessions
            # Check for unclosed session
            if log.active_session():
                typer.echo(f"Cannot compile {resolved_date}: log has an unclosed session. Run 'faff stop' first.", err=True)
                raise typer.Exit(1)

            for aud in audiences:
                compiled_timesheet = ws.timesheets.compile(log, aud)
                # Sign the timesheet if signing_ids are configured
                signing_ids = aud.config.get('signing_ids', [])
                if signing_ids:
                    signed = False
                    for signing_id in signing_ids:
                        key = ws.identities.get_identity(signing_id)
                        if key:
                            compiled_timesheet = compiled_timesheet.sign(signing_id, bytes(key))
                            signed = True
                        else:
                            typer.echo(f"Warning: No identity key found for {signing_id}", err=True)

                    if signed:
                        ws.timesheets.write_timesheet(compiled_timesheet)
                        typer.echo(f"Compiled and signed timesheet for {resolved_date} using {aud.id}.")
                    else:
                        ws.timesheets.write_timesheet(compiled_timesheet)
                        typer.echo(f"Warning: Compiled unsigned timesheet for {resolved_date} using {aud.id} (no valid signing keys)", err=True)
                else:
                    ws.timesheets.write_timesheet(compiled_timesheet)
                    typer.echo(f"Warning: Compiled unsigned timesheet for {resolved_date} using {aud.id} (no signing_ids configured)", err=True)
        else:
            # No date provided - find all logs that need compiling
            log_dates = ws.logs.list_log_dates()
            existing_timesheets = ws.timesheets.list_timesheets()

            # Build a set of (audience_id, date) tuples for existing timesheets
            existing = {(ts.meta.audience_id, ts.date) for ts in existing_timesheets}

            compiled_count = 0
            skipped_unclosed = []
            for log_date in log_dates:
                log = ws.logs.get_log(log_date)
                if not log:
                    continue

                # FIXME: This check should be in faff-core, not faff-cli
                # The compile_time_sheet method should refuse to compile logs with active sessions
                # Check for unclosed session
                if log.active_session():
                    skipped_unclosed.append(log_date)
                    continue

                for aud in audiences:
                    if (aud.id, log_date) not in existing:
                        compiled_timesheet = ws.timesheets.compile(log, aud)
                        # Sign the timesheet if signing_ids are configured (even if empty)
                        is_empty = len(compiled_timesheet.timeline) == 0
                        signing_ids = aud.config.get('signing_ids', [])

                        if signing_ids:
                            signed = False
                            for signing_id in signing_ids:
                                key = ws.identities.get_identity(signing_id)
                                if key:
                                    compiled_timesheet = compiled_timesheet.sign(signing_id, bytes(key))
                                    signed = True
                                else:
                                    typer.echo(f"Warning: No identity key found for {signing_id}", err=True)

                            if signed:
                                ws.timesheets.write_timesheet(compiled_timesheet)
                                if is_empty:
                                    typer.echo(f"Compiled and signed empty timesheet for {log_date} using {aud.id} (no relevant sessions).")
                                else:
                                    typer.echo(f"Compiled and signed timesheet for {log_date} using {aud.id}.")
                            else:
                                ws.timesheets.write_timesheet(compiled_timesheet)
                                if is_empty:
                                    typer.echo(f"Warning: Compiled unsigned empty timesheet for {log_date} using {aud.id} (no valid signing keys)", err=True)
                                else:
                                    typer.echo(f"Warning: Compiled unsigned timesheet for {log_date} using {aud.id} (no valid signing keys)", err=True)
                        else:
                            ws.timesheets.write_timesheet(compiled_timesheet)
                            if is_empty:
                                typer.echo(f"Warning: Compiled unsigned empty timesheet for {log_date} using {aud.id} (no signing_ids configured)", err=True)
                            else:
                                typer.echo(f"Warning: Compiled unsigned timesheet for {log_date} using {aud.id} (no signing_ids configured)", err=True)

                        compiled_count += 1

            if skipped_unclosed:
                typer.echo(f"\nSkipped {len(skipped_unclosed)} log(s) with unclosed sessions:", err=True)
                for log_date in skipped_unclosed:
                    typer.echo(f"  - {log_date} (run 'faff stop' to close the active session)", err=True)

            if compiled_count == 0 and not skipped_unclosed:
                typer.echo("All logs already have compiled timesheets.")
    except Exception as e:
        typer.echo(f"Error compiling timesheet: {e}", err=True)
        raise typer.Exit(1)

@cli.command(rich_help_panel="Compile and Submit Timesheets")
def push(
    ctx: typer.Context,
    date: str = typer.Argument(None, help="Specific date to push (omit for all unsubmitted)"),
    audience: str = typer.Option(None, "--audience", "-a", help="Specific audience (omit for all)"),
):
    """
    Submit timesheets to audiences.

    Pushes compiled timesheets to their configured audiences. By default, pushes
    all unsubmitted timesheets. Specify a date to force push a specific date.

    Examples:
        faff push
        faff push 2025-01-15
        faff push --audience element
        faff push yesterday --audience mycompany
    """
    try:
        ws: Workspace = ctx.obj

        if date:
            # Specific date provided - push that date
            resolved_date = ws.parse_natural_date(date)
            audiences = ws.timesheets.audiences()

            if audience:
                audiences = [a for a in audiences if a.id == audience]
                if len(audiences) == 0:
                    typer.echo(f"Unknown audience: {audience}", err=True)
                    raise typer.Exit(1)

            for aud in audiences:
                timesheet = ws.timesheets.get_timesheet(aud.id, resolved_date)
                if timesheet:
                    ws.timesheets.submit(timesheet)
                    typer.echo(f"Pushed timesheet for {resolved_date} to {aud.id}.")
                else:
                    typer.echo(f"No timesheet found for {aud.id} on {resolved_date}. Did you run 'faff compile' first?", err=True)
        else:
            # No date provided - push all unsubmitted timesheets
            all_timesheets = ws.timesheets.list_timesheets()
            unsubmitted = [ts for ts in all_timesheets if ts.meta.submitted_at is None]

            if audience:
                unsubmitted = [ts for ts in unsubmitted if ts.meta.audience_id == audience]

            if len(unsubmitted) == 0:
                typer.echo("All timesheets have been submitted.")
            else:
                for timesheet in unsubmitted:
                    ws.timesheets.submit(timesheet)
                    typer.echo(f"Pushed timesheet for {timesheet.date} to {timesheet.meta.audience_id}.")
    except Exception as e:
        typer.echo(f"Error pushing timesheet: {e}", err=True)
        raise typer.Exit(1)

@cli.command(rich_help_panel="Track your Time")
def status(ctx: typer.Context):
    """
    Show ledger status.

    Displays the pull -> log -> compile -> push workflow status:
    - Active plans and freshness
    - Today's tracking summary
    - Logs needing compilation
    - Timesheets needing submission

    Examples:
        faff status
    """
    from rich.console import Console

    try:
        ws: Workspace = ctx.obj
        console = Console(highlight=False)

        # 1. PULL - Show plan status and freshness
        console.print("[bold]Plans:[/bold]")

        plans = ws.plans.get_plans(ws.today())

        # Check if plans are stale
        stale_plans = [s for s, p in plans.items() if (ws.today() - p.valid_from).days > 7]
        if stale_plans:
            console.print(f"  [dim]Some plans are stale. Run[/dim] [cyan]faff pull[/cyan] [dim]to refresh:[/dim]")

        if plans:
            for source, plan in plans.items():
                age_days = (ws.today() - plan.valid_from).days
                if age_days == 0:
                    freshness = "[green]today[/green]"
                elif age_days == 1:
                    freshness = "[yellow]yesterday[/yellow]"
                elif age_days <= 7:
                    freshness = f"[yellow]{age_days}d ago[/yellow]"
                else:
                    freshness = f"[red]{age_days}d ago[/red]"

                intent_count = len(plan.intents)
                console.print(f"  [cyan]{source}[/cyan] · {intent_count} intent(s) · pulled {freshness}")

        else:
            console.print("[yellow]  No plans available[/yellow]")
            console.print(f"  [dim]Run[/dim] [cyan]faff pull[/cyan]")

        console.print()

        # 2. LOG - Today's tracking status
        console.print("[bold]Today:[/bold]")
        log = ws.logs.get_log(ws.today())
        total_seconds = log.total_recorded_time().total_seconds()
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)

        if hours > 0:
            console.print(f"  {hours}h {minutes}m tracked")
        else:
            console.print(f"  {minutes}m tracked")

        active_session = log.active_session()
        if active_session:
            duration_minutes = int(active_session.elapsed(ws.now()).total_seconds() / 60)
            if active_session.note:
                console.print(f"  [green]●[/green] {active_session.intent.alias} [dim]({active_session.note})[/dim] · {duration_minutes}m")
            else:
                console.print(f"  [green]●[/green] {active_session.intent.alias} · {duration_minutes}m")
        else:
            console.print("  [dim]○ Not tracking[/dim]")

        console.print()

        # 3. COMPILE - Check what needs compiling
        console.print("[bold]Logs to Compile:[/bold]")
        console.print(f"  [dim]Ready to Compile. Run[/dim] [cyan]faff compile[/cyan]:")
        log_dates = ws.logs.list_log_dates()
        existing_timesheets = ws.timesheets.list_timesheets()
        audiences = ws.timesheets.audiences()
        stale = ws.timesheets.find_stale_timesheets()

        # Build a set of (audience_id, date) tuples for existing timesheets
        existing = {(ts.meta.audience_id, ts.date) for ts in existing_timesheets}

        needs_compiling = []
        has_unclosed = []
        for log_date in log_dates:
            log = ws.logs.get_log(log_date)
            if not log:
                continue

            # Check if this log needs compiling for any audience
            needs_compile_for_audiences = [aud.id for aud in audiences if (aud.id, log_date) not in existing]

            if needs_compile_for_audiences:
                total_hours = log.total_recorded_time().total_seconds() / 3600
                if log.active_session():
                    has_unclosed.append((log_date, total_hours, needs_compile_for_audiences))
                else:
                    needs_compiling.append((log_date, total_hours, needs_compile_for_audiences))

        # Only unsubmitted stale timesheets need recompilation
        stale_unsubmitted = [ts for ts in stale if ts.meta.submitted_at is None]
        stale_submitted = [ts for ts in stale if ts.meta.submitted_at is not None]

        # Show ready to compile first
        total_needing_compile = len(needs_compiling) + len(stale_unsubmitted)
        if total_needing_compile > 0:
            if needs_compiling:
                for log_date, hours, audience_ids in sorted(needs_compiling, key=lambda x: x[0]):
                    console.print(f"  {log_date} · [cyan]{hours:>4.1f}h[/cyan] → {', '.join(audience_ids)}")

            if stale_unsubmitted:
                for ts in sorted(stale_unsubmitted, key=lambda t: t.date):
                    hours = sum(s.duration.total_seconds() for s in ts.timeline) / 3600
                    console.print(f"  {ts.date} · [cyan]{hours:>4.1f}h[/cyan] ({ts.meta.audience_id}) [yellow]stale[/yellow]")

            total_hours = sum(h for _, h, _ in needs_compiling) + sum(sum(s.duration.total_seconds() for s in ts.timeline) / 3600 for ts in stale_unsubmitted)
            console.print(f"  [dim]{total_needing_compile} log(s),[/dim] [cyan]{total_hours:.1f}h[/cyan] [dim]total[/dim]")

        # Show blockers after (unclosed sessions)
        if has_unclosed:
            if total_needing_compile > 0:
                console.print()
            console.print("  [red]Blocked.[/red] [dim]Run[/dim] [cyan]faff stop[/cyan] [dim]or[/dim] [cyan]faff log edit <date>[/cyan][dim]:[/dim]")
            for log_date, hours, audience_ids in has_unclosed:
                console.print(f"  {log_date} · [cyan]{hours:>4.1f}h[/cyan]")

        # If nothing to compile and no blockers
        if total_needing_compile == 0 and not has_unclosed:
            console.print("  [dim]✓ All logs compiled[/dim]")

        console.print()

        # 4. PUSH - Check what needs submission
        console.print("[bold]Timesheets to Push:[/bold]")
        failed = ws.timesheets.find_failed_submissions()
        unsubmitted = [ts for ts in existing_timesheets if ts.meta.submitted_at is None]

        # Exclude stale unsubmitted from the push list (they need recompiling first)
        stale_dates = {(ts.meta.audience_id, ts.date) for ts in stale_unsubmitted}
        unsubmitted_ready = [ts for ts in unsubmitted if (ts.meta.audience_id, ts.date) not in stale_dates]

        # Show ready to push first
        total_needing_push = len(unsubmitted_ready) + len(failed) + len(stale_submitted)
        if total_needing_push > 0:
            if unsubmitted_ready:
                console.print(f"  [dim]Ready to Push. Run[/dim] [cyan]faff push[/cyan]:")
                for ts in sorted(unsubmitted_ready, key=lambda t: t.date):
                    hours = sum(s.duration.total_seconds() for s in ts.timeline) / 3600
                    console.print(f"  {ts.date} · [cyan]{hours:>4.1f}h[/cyan] → {ts.meta.audience_id}")

            # Show failed submissions
            if failed:
                if unsubmitted_ready:
                    console.print()
                console.print("  [red]Failed.[/red] [dim]Fix errors and run[/dim] [cyan]faff push[/cyan]:")
                for ts in sorted(failed, key=lambda t: t.date):
                    hours = sum(s.duration.total_seconds() for s in ts.timeline) / 3600
                    error = ts.meta.submission_error
                    if len(error) > 50:
                        error = error[:47] + "..."
                    console.print(f"  {ts.date} · [cyan]{hours:>4.1f}h[/cyan] → {ts.meta.audience_id} [red]{error}[/red]")

            # Warn about submitted stale timesheets
            if stale_submitted:
                if unsubmitted_ready or failed:
                    console.print()
                console.print("  [yellow]Stale (already submitted).[/yellow] [dim]Manual review needed:[/dim]")
                for ts in sorted(stale_submitted, key=lambda t: t.date):
                    hours = sum(s.duration.total_seconds() for s in ts.timeline) / 3600
                    submitted = ts.meta.submitted_at.strftime("%Y-%m-%d")
                    console.print(f"  {ts.date} · [cyan]{hours:>4.1f}h[/cyan] ({ts.meta.audience_id}) [dim]submitted {submitted}[/dim]")
        else:
            console.print("  [dim]✓ All timesheets submitted[/dim]")

    except Exception as e:
        typer.echo(f"Error getting status: {e}", err=True)
        raise typer.Exit(1)

# Register log and sql after status
cli.add_typer(log.app, name="log", rich_help_panel="Track your Time")
cli.add_typer(sql.app, name="sql", rich_help_panel="Track your Time")

@cli.command(rich_help_panel="Track your Time")
def stop(ctx: typer.Context):
    """
    Stop the current session.

    Ends the currently active time tracking session.

    Examples:
        faff stop
    """
    try:
        import humanize
        ws: Workspace = ctx.obj

        # Get the current log to see what we're stopping
        log = ws.logs.get_log(ws.today())
        active = log.active_session()

        if not active:
            typer.echo("No active session to stop", err=True)
            raise typer.Exit(1)

        # Capture the details before stopping
        intent_alias = active.intent.alias
        start_time = active.start

        # Stop the session
        ws.logs.stop_current_session()

        # Calculate duration
        end_time = ws.now()
        duration = end_time - start_time

        # Show feedback
        typer.echo(f"Stopped '{intent_alias}'")
        typer.echo(f"  Started: {start_time.strftime('%H:%M:%S')}")
        typer.echo(f"  Ended:   {end_time.strftime('%H:%M:%S')}")
        typer.echo(f"  Duration: {humanize.precisedelta(duration, minimum_unit='seconds')}")
    except Exception as e:
        typer.echo(f"Error stopping session: {e}", err=True)
        raise typer.Exit(1)

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rollagent import __version__
from rollagent.engine import Engine, EngineError
from rollagent.models import Action, ActionStatus, ExecMode
from rollagent.paths import db_path, default_home, effects_dir
from rollagent.store import Store

app = typer.Typer(
    name="rollagent",
    help="Optimistic rollups for AI agent actions.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _home(path: Optional[Path]) -> Path:
    return path if path else default_home()


def _engine(home: Path) -> Engine:
    store = Store(db_path(home))
    return Engine(store, effects_dir=effects_dir(home))


def _die(msg: str, code: int = 1) -> None:
    console.print(f"[red]error:[/red] {msg}")
    raise typer.Exit(code)


def _print_action(action: Action, challenges: list | None = None) -> None:
    color = {
        ActionStatus.PENDING: "yellow",
        ActionStatus.CHALLENGED: "magenta",
        ActionStatus.FINAL: "green",
        ActionStatus.REVERTED: "red",
    }.get(action.status, "white")

    body = (
        f"[bold]{action.id}[/bold]  [{color}]{action.status.value}[/{color}]\n"
        f"type:     {action.type}  mode: {action.mode.value}\n"
        f"summary:  {action.summary}\n"
        f"window:   {action.window_seconds}s  finalizes_at: {action.finalizes_at}\n"
        f"actor:    {action.actor}\n"
        f"payload:  {json.dumps(action.payload, ensure_ascii=False)}"
    )
    if action.executed_at:
        body += f"\nexecuted: {action.executed_at}"
    if action.finalized_at:
        body += f"\nclosed:   {action.finalized_at}"
    if action.revert_reason:
        body += f"\nrevert:   {action.revert_reason}"

    console.print(Panel(body, title="action", border_style=color))

    if challenges:
        table = Table(title="challenges", show_header=True, header_style="bold")
        table.add_column("id")
        table.add_column("status")
        table.add_column("challenger")
        table.add_column("evidence")
        for ch in challenges:
            table.add_row(ch.id, ch.status.value, ch.challenger, ch.evidence[:60])
        console.print(table)


@app.command()
def version() -> None:
    """Print version."""
    console.print(__version__)


@app.command("init")
def init_cmd(
    home: Optional[Path] = typer.Option(None, "--home", help="Data directory (default ~/.rollagent)"),
) -> None:
    """Initialize local store."""
    h = _home(home)
    h.mkdir(parents=True, exist_ok=True)
    effects_dir(h).mkdir(parents=True, exist_ok=True)
    eng = _engine(h)
    eng.store.close()
    console.print(f"[green]initialized[/green] {h}")
    console.print(f"  db:      {db_path(h)}")
    console.print(f"  effects: {effects_dir(h)}")


@app.command()
def propose(
    type: str = typer.Argument(..., help="Action type, e.g. publish_tip | write_file | shell"),
    payload: Optional[str] = typer.Option(
        None, "--payload", "-p", help="JSON payload object"
    ),
    window: int = typer.Option(900, "--window", "-w", help="Challenge window in seconds"),
    mode: str = typer.Option("declare", "--mode", "-m", help="declare | eager"),
    actor: str = typer.Option("agent", "--actor"),
    summary: str = typer.Option("", "--summary", "-s"),
    match: Optional[str] = typer.Option(None, "--match", help="Shortcut for publish_tip"),
    pick: Optional[str] = typer.Option(None, "--pick", help="Shortcut for publish_tip"),
    stake: Optional[str] = typer.Option(None, "--stake", help="Shortcut for publish_tip"),
    path: Optional[str] = typer.Option(None, "--path", help="Shortcut for write_file"),
    content: Optional[str] = typer.Option(None, "--content", help="Shortcut for write_file"),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Propose an action (enters PENDING challenge window)."""
    data: dict[str, Any] = {}
    if payload:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            _die(f"invalid --payload JSON: {e}")

    if type == "publish_tip":
        if match:
            data.setdefault("match", match)
        if pick:
            data.setdefault("pick", pick)
        if stake:
            data.setdefault("stake", stake)
    if type == "write_file":
        if path:
            data.setdefault("path", path)
        if content is not None:
            data.setdefault("content", content)

    try:
        eng = _engine(_home(home))
        action = eng.propose(
            type,
            data,
            window_seconds=window,
            mode=ExecMode(mode),
            actor=actor,
            summary=summary,
        )
    except (EngineError, ValueError) as e:
        _die(str(e))

    console.print("[green]proposed[/green] — status PENDING (challenge window open)")
    _print_action(action)


@app.command("list")
def list_cmd(
    status: Optional[str] = typer.Option(None, "--status", help="pending|challenged|final|reverted"),
    limit: int = typer.Option(20, "--limit", "-n"),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """List actions."""
    eng = _engine(_home(home))
    actions = eng.store.list_actions(status=status, limit=limit)
    if not actions:
        console.print("[dim]no actions[/dim]")
        return

    table = Table(title="actions", show_lines=False)
    table.add_column("id", style="cyan")
    table.add_column("status")
    table.add_column("type")
    table.add_column("summary")
    table.add_column("finalizes_at")
    for a in actions:
        table.add_row(a.id, a.status.value, a.type, a.summary[:48], a.finalizes_at)
    console.print(table)


@app.command()
def show(
    action_id: str = typer.Argument(...),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Show one action + challenges."""
    eng = _engine(_home(home))
    action = eng.store.get_action(action_id)
    if not action:
        _die(f"unknown action: {action_id}")
    _print_action(action, eng.store.list_challenges(action_id))


@app.command()
def challenge(
    action_id: str = typer.Argument(...),
    evidence: str = typer.Option(..., "--evidence", "-e", help="Why this action should not finalize"),
    challenger: str = typer.Option("human", "--challenger", "-c"),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Open a challenge against a pending action."""
    try:
        eng = _engine(_home(home))
        action, ch = eng.challenge(action_id, evidence, challenger=challenger)
    except EngineError as e:
        _die(str(e))
    console.print(f"[magenta]challenged[/magenta] {action_id} → {ch.id}")
    _print_action(action, eng.store.list_challenges(action_id))


@app.command("accept")
def accept_cmd(
    challenge_id: str = typer.Argument(..., help="Challenge id (chg_...)"),
    note: str = typer.Option("challenge accepted", "--note"),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Accept a challenge → action REVERTED."""
    try:
        eng = _engine(_home(home))
        action = eng.accept_challenge(challenge_id, note=note)
    except EngineError as e:
        _die(str(e))
    console.print(f"[red]reverted[/red] {action.id}")
    _print_action(action, eng.store.list_challenges(action.id))


@app.command("reject")
def reject_cmd(
    challenge_id: str = typer.Argument(...),
    note: str = typer.Option("challenge rejected", "--note"),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Reject a challenge (action returns to pending / may finalize)."""
    try:
        eng = _engine(_home(home))
        action = eng.reject_challenge(challenge_id, note=note)
    except EngineError as e:
        _die(str(e))
    console.print(f"[yellow]challenge rejected[/yellow] → action {action.status.value}")
    _print_action(action, eng.store.list_challenges(action.id))


@app.command()
def finalize(
    action_id: str = typer.Argument(...),
    force: bool = typer.Option(False, "--force", help="Skip remaining window (demo/dev)"),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Finalize an action after the challenge window (or --force)."""
    try:
        eng = _engine(_home(home))
        action = eng.finalize(action_id, force=force)
    except EngineError as e:
        _die(str(e))
    console.print(f"[green]final[/green] {action.id}")
    _print_action(action)


@app.command()
def tick(
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Auto-finalize all pending actions whose window elapsed."""
    eng = _engine(_home(home))
    done = eng.tick()
    if not done:
        console.print("[dim]nothing to finalize[/dim]")
        return
    console.print(f"[green]finalized {len(done)} action(s)[/green]")
    for a in done:
        console.print(f"  • {a.id}  {a.summary}")


@app.command()
def demo(
    home: Optional[Path] = typer.Option(
        None, "--home", help="Isolated demo home (default: ~/.rollagent/demo)"
    ),
) -> None:
    """30-second walkthrough: propose → challenge → revert, then happy path."""
    h = home if home else default_home() / "demo"
    # Fresh demo store
    if h.exists():
        import shutil

        shutil.rmtree(h)
    h.mkdir(parents=True, exist_ok=True)
    eng = _engine(h)

    console.print(
        Panel(
            "[bold]rollagent demo[/bold]\n"
            "Optimistic rollups for agent actions:\n"
            "  propose → PENDING window → challenge? → FINAL or REVERTED",
            border_style="cyan",
        )
    )

    console.print("\n[bold]1) Agent proposes a tip (declare mode, 60s window)[/bold]")
    a1 = eng.propose(
        "publish_tip",
        {"match": "Man City vs Arsenal", "pick": "City -0.5", "stake": "2u"},
        window_seconds=60,
        mode=ExecMode.DECLARE,
        actor="tip-agent",
    )
    _print_action(a1)

    console.print("\n[bold]2) Human/bot challenges with evidence[/bold]")
    a1, ch = eng.challenge(
        a1.id,
        evidence="Arsenal priced too short after lineup leak; edge negative",
        challenger="odds-bot",
    )
    _print_action(a1, eng.store.list_challenges(a1.id))

    console.print("\n[bold]3) Challenge ACCEPTED → action REVERTED (never published)[/bold]")
    a1 = eng.accept_challenge(ch.id)
    _print_action(a1)

    console.print("\n[bold]4) Happy path: propose another tip, no challenge, force finalize[/bold]")
    a2 = eng.propose(
        "publish_tip",
        {"match": "Liverpool vs Chelsea", "pick": "Over 2.5", "stake": "1u"},
        window_seconds=30,
        mode=ExecMode.DECLARE,
        actor="tip-agent",
    )
    a2 = eng.finalize(a2.id, force=True)
    _print_action(a2)

    tips = effects_dir(h) / "tips.jsonl"
    console.print(
        Panel(
            f"[green]demo complete[/green]\n"
            f"data:  {h}\n"
            f"tips:  {tips if tips.exists() else '(none)'}\n\n"
            "Next:\n"
            "  rollagent init\n"
            "  rollagent propose publish_tip --match 'A vs B' --pick 'A -0.5' --stake 1u -w 120\n"
            "  rollagent list\n"
            "  rollagent challenge act_xxx -e 'reason'\n"
            "  rollagent finalize act_xxx --force",
            title="done",
            border_style="green",
        )
    )
    eng.store.close()


def main() -> None:
    app()


if __name__ == "__main__":
    main()

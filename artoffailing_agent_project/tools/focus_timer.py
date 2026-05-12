"""
focus_timer.py — blacksun-agent tool
Pomodoro-style focus sessions with a persistent work log.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import json
import time as _time
from datetime import datetime, date
from pathlib import Path
from mcp.server import FastMCP

_BASE = Path(__file__).resolve().parent.parent
LOG_FILE = _BASE / "logs" / "focus_log.json"
STATE_FILE = _BASE / "logs" / "focus_state.json"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_log() -> list[dict]:
    if not LOG_FILE.exists():
        return []
    return json.loads(LOG_FILE.read_text())


def _save_log(log: list[dict]):
    LOG_FILE.write_text(json.dumps(log, indent=2))


def _load_state() -> dict | None:
    if not STATE_FILE.exists():
        return None
    return json.loads(STATE_FILE.read_text())


def _save_state(state: dict | None):
    if state is None:
        STATE_FILE.unlink(missing_ok=True)
    else:
        STATE_FILE.write_text(json.dumps(state, indent=2))


def register_focus_timer(mcp: FastMCP):

    @mcp.tool()
    def focus_start(label: str, minutes: int = 25) -> str:
        """
        Start a named focus session.

        Args:
            label:   What you're working on (e.g. "Varonis SaaS design doc")
            minutes: Session length in minutes (default 25 — classic Pomodoro)
        """
        existing = _load_state()
        if existing:
            elapsed = int((_time.time() - existing["started_at"]) / 60)
            return (
                f"Session already running: '{existing['label']}' "
                f"({elapsed} min in). "
                f"Run focus_stop() to end it first."
            )
        state = {
            "label": label,
            "minutes": minutes,
            "started_at": _time.time(),
            "started_str": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        _save_state(state)
        return (
            f"Focus session started: **{label}**\n"
            f"Duration: {minutes} min\n"
            f"Started: {state['started_str']}\n\n"
            f"Run `focus_stop()` when done (or `focus_status()` to check in)."
        )

    @mcp.tool()
    def focus_stop(notes: str = "") -> str:
        """
        End the current focus session and log it.

        Args:
            notes: Optional notes about what was accomplished
        """
        state = _load_state()
        if not state:
            return "No active session. Use focus_start() to begin one."

        ended_at = _time.time()
        actual_minutes = round((ended_at - state["started_at"]) / 60, 1)
        planned_minutes = state["minutes"]

        entry = {
            "date": date.today().isoformat(),
            "label": state["label"],
            "planned_min": planned_minutes,
            "actual_min": actual_minutes,
            "started": state["started_str"],
            "ended": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "notes": notes,
            "completed": actual_minutes >= planned_minutes * 0.8,
        }
        log = _load_log()
        log.append(entry)
        _save_log(log)
        _save_state(None)

        status = "Completed" if entry["completed"] else "Stopped early"
        result = (
            f"Session ended — {status}\n\n"
            f"- Label: {entry['label']}\n"
            f"- Planned: {planned_minutes} min\n"
            f"- Actual: {actual_minutes} min\n"
        )
        if notes:
            result += f"- Notes: {notes}\n"
        return result

    @mcp.tool()
    def focus_status() -> str:
        """
        Check if a focus session is running and how long it's been going.
        """
        state = _load_state()
        if not state:
            return "No active focus session."
        elapsed = (_time.time() - state["started_at"]) / 60
        remaining = state["minutes"] - elapsed
        pct = min(100, int((elapsed / state["minutes"]) * 100))
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)

        if remaining > 0:
            return (
                f"In session: **{state['label']}**\n"
                f"Progress: [{bar}] {pct}%\n"
                f"Elapsed: {int(elapsed)} min / {state['minutes']} min\n"
                f"Remaining: {max(0, int(remaining))} min"
            )
        else:
            overtime = int(abs(remaining))
            return (
                f"Session complete (running {overtime} min over): **{state['label']}**\n"
                f"Run `focus_stop()` to log it."
            )

    @mcp.tool()
    def focus_log(days: int = 7) -> str:
        """
        Show the focus work log as Markdown.

        Args:
            days: How many days back to show (default 7)
        """
        from datetime import timedelta
        log = _load_log()
        if not log:
            return "No focus sessions logged yet."

        cutoff = (date.today() - timedelta(days=days)).isoformat()
        recent = [e for e in log if e["date"] >= cutoff]

        if not recent:
            return f"No sessions in the last {days} days."

        # Group by date
        by_date: dict[str, list] = {}
        for e in recent:
            by_date.setdefault(e["date"], []).append(e)

        total_min = sum(e["actual_min"] for e in recent)
        total_sessions = len(recent)
        lines = [
            f"# Focus log — last {days} days\n",
            f"**{total_sessions} sessions · {round(total_min / 60, 1)} hrs total**\n",
        ]

        for d in sorted(by_date.keys(), reverse=True):
            day_sessions = by_date[d]
            day_min = sum(e["actual_min"] for e in day_sessions)
            dt = datetime.fromisoformat(d).strftime("%A, %b %#d")
            lines.append(f"## {dt} — {round(day_min / 60, 1)} hrs\n")
            for e in day_sessions:
                check = "x" if e["completed"] else " "
                lines.append(
                    f"- [{check}] {e['started'][11:16]}–{e['ended'][11:16]} "
                    f"({e['actual_min']} min) **{e['label']}**"
                )
                if e.get("notes"):
                    lines.append(f"  _{e['notes']}_")
            lines.append("")

        return "\n".join(lines).strip()

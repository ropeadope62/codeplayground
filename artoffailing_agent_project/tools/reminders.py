"""
Reminders — set, list, and dismiss time-based reminders.

Stored as a JSON file (notes/reminders.json).
Each reminder has a due date/time, title, optional notes, and a status.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import json
from datetime import datetime
from pathlib import Path

from mcp.server import FastMCP

_BASE = Path(__file__).resolve().parent.parent
REMINDERS_FILE = _BASE / "notes" / "reminders.json"
REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)

_DT_FORMAT = "%Y-%m-%d %H:%M"
_DATE_FORMAT = "%Y-%m-%d"


def _load() -> list[dict]:
    if not REMINDERS_FILE.exists():
        return []
    return json.loads(REMINDERS_FILE.read_text(encoding="utf-8"))


def _save(reminders: list[dict]):
    REMINDERS_FILE.write_text(json.dumps(reminders, indent=2), encoding="utf-8")


def _parse_due(due: str) -> str:
    """Accept 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM' and return a normalised string."""
    due = due.strip()
    for fmt in (_DT_FORMAT, _DATE_FORMAT):
        try:
            return datetime.strptime(due, fmt).strftime(_DT_FORMAT)
        except ValueError:
            continue
    raise ValueError(
        f"Invalid due date/time '{due}'. Use 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM'."
    )


def _fmt_reminder(r: dict) -> str:
    status = "✓" if r.get("done") else "○"
    line = f"{status} #{r['id']} [{r['due']}] {r['title']}"
    if r.get("notes"):
        line += f"\n    {r['notes']}"
    return line


def register_reminders(mcp: FastMCP):

    @mcp.tool()
    def add_reminder(title: str, due: str, notes: str = "") -> str:
        """
        Set a reminder.

        Args:
            title: Short description of what to remember.
            due:   When the reminder is due. Accepts 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM'.
            notes: Optional extra detail.

        Returns:
            Confirmation with the saved reminder ID and due time.
        """
        try:
            due_normalised = _parse_due(due)
        except ValueError as exc:
            return str(exc)

        reminders = _load()
        used_ids = {r["id"] for r in reminders}
        new_id = 1
        while new_id in used_ids:
            new_id += 1

        entry = {
            "id":      new_id,
            "title":   title.strip(),
            "due":     due_normalised,
            "notes":   notes.strip(),
            "created": datetime.now().strftime(_DT_FORMAT),
            "done":    False,
        }
        reminders.append(entry)
        reminders.sort(key=lambda r: r["due"])
        _save(reminders)
        return f"Reminder #{new_id} set for {due_normalised}: {title}"

    @mcp.tool()
    def list_reminders(include_done: bool = False, query: str = "") -> str:
        """
        List reminders.

        Args:
            include_done: If True, include dismissed reminders. Default False.
            query:        Optional keyword filter applied to title and notes.

        Returns:
            Formatted list of reminders sorted by due date.
        """
        reminders = _load()
        if not include_done:
            reminders = [r for r in reminders if not r.get("done")]
        if query:
            q = query.lower()
            reminders = [
                r for r in reminders
                if q in r["title"].lower() or q in r.get("notes", "").lower()
            ]
        if not reminders:
            return "No reminders found."

        now = datetime.now().strftime(_DT_FORMAT)
        lines = []
        for r in reminders:
            line = _fmt_reminder(r)
            if not r.get("done") and r["due"] < now:
                line += "  ⚠ OVERDUE"
            lines.append(line)
        return "\n".join(lines)

    @mcp.tool()
    def dismiss_reminder(reminder_id: int) -> str:
        """
        Mark a reminder as done (dismissed).

        Args:
            reminder_id: The numeric ID of the reminder to dismiss.
        """
        reminders = _load()
        for r in reminders:
            if r["id"] == reminder_id:
                if r.get("done"):
                    return f"Reminder #{reminder_id} is already dismissed."
                r["done"] = True
                _save(reminders)
                return f"Reminder #{reminder_id} dismissed: {r['title']}"
        return f"Reminder #{reminder_id} not found."

    @mcp.tool()
    def delete_reminder(reminder_id: int) -> str:
        """
        Permanently delete a reminder.

        Args:
            reminder_id: The numeric ID of the reminder to delete.
        """
        reminders = _load()
        before = len(reminders)
        reminders = [r for r in reminders if r["id"] != reminder_id]
        if len(reminders) == before:
            return f"Reminder #{reminder_id} not found."
        _save(reminders)
        return f"Reminder #{reminder_id} deleted."

    @mcp.tool()
    def due_reminders() -> str:
        """
        Return all reminders that are due now or overdue (and not yet dismissed).
        Useful for a startup check or briefing.
        """
        reminders = _load()
        now = datetime.now().strftime(_DT_FORMAT)
        due = [r for r in reminders if not r.get("done") and r["due"] <= now]
        if not due:
            return "No reminders are currently due."
        lines = [f"⚠ {len(due)} reminder(s) due:\n"]
        lines += [_fmt_reminder(r) for r in due]
        return "\n".join(lines)

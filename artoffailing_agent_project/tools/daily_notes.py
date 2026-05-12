"""
daily_notes.py — Work and personal notes with daily/weekly summaries.

Stores timestamped entries as JSON in notes/daily/YYYY-MM-DD.json.
Each entry has a category (work | personal), optional tags, and text.
Daily and weekly summary tools compile notes into structured Markdown.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import json
from pathlib import Path
from datetime import datetime, date, timedelta
from mcp.server import FastMCP

BASE_DIR = Path(__file__).resolve().parent.parent / "notes" / "daily"
BASE_DIR.mkdir(parents=True, exist_ok=True)

CATEGORIES = ("work", "personal")


def _day_path(d: str = "") -> Path:
    if not d:
        d = date.today().isoformat()
    return BASE_DIR / f"{d}.json"


def _load_day(d: str = "") -> list[dict]:
    p = _day_path(d)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def _save_day(entries: list[dict], d: str = ""):
    p = _day_path(d)
    p.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _add_entry(text: str, category: str, tags: str = "", note_date: str = "") -> str:
    if category not in CATEGORIES:
        return f"Invalid category '{category}'. Must be: {', '.join(CATEGORIES)}"
    d = note_date or date.today().isoformat()
    entries = _load_day(d)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    entry = {
        "id": len(entries) + 1,
        "time": datetime.now().strftime("%H:%M"),
        "category": category,
        "text": text.strip(),
        "tags": tag_list,
        "date": d,
    }
    entries.append(entry)
    _save_day(entries, d)
    tag_str = f" [{', '.join(tag_list)}]" if tag_list else ""
    return f"Saved {category} note #{entry['id']}{tag_str}: {text[:80]}"


def _build_daily_summary(d: str = "") -> str:
    d = d or date.today().isoformat()
    entries = _load_day(d)
    try:
        day_name = datetime.strptime(d, "%Y-%m-%d").strftime("%A, %B %d, %Y")
    except ValueError:
        day_name = d

    lines = [f"# Daily Summary — {day_name}\n"]

    if not entries:
        lines.append("_No notes recorded for this day._")
        return "\n".join(lines)

    for cat, label in [("work", "Work"), ("personal", "Personal")]:
        cat_entries = [e for e in entries if e["category"] == cat]
        if not cat_entries:
            continue
        lines.append(f"## {label} ({len(cat_entries)} notes)\n")
        for e in cat_entries:
            tag_str = " " + " ".join(f"`#{t}`" for t in e["tags"]) if e.get("tags") else ""
            lines.append(f"- **{e['time']}** — {e['text']}{tag_str}")
        lines.append("")

    # Tag overview
    all_tags: dict[str, int] = {}
    for e in entries:
        for t in e.get("tags", []):
            all_tags[t] = all_tags.get(t, 0) + 1
    if all_tags:
        lines.append("## Tags\n")
        for tag, count in sorted(all_tags.items(), key=lambda x: -x[1]):
            lines.append(f"- #{tag} ({count})")
        lines.append("")

    lines.append(f"---\n_Total: {len(entries)} notes_")
    return "\n".join(lines)


def _build_weekly_summary(weeks_back: int = 0) -> str:
    today = date.today()
    start = today - timedelta(days=today.weekday() + weeks_back * 7)
    end = start + timedelta(days=6)
    week_label = f"{start.strftime('%b %d')}–{end.strftime('%b %d, %Y')}"

    lines = [f"# Weekly Summary — {week_label}\n"]

    all_entries: list[dict] = []
    days_active = 0
    for i in range(7):
        d = (start + timedelta(days=i)).isoformat()
        day_entries = _load_day(d)
        if day_entries:
            days_active += 1
            all_entries.extend(day_entries)

    if not all_entries:
        lines.append("_No notes recorded this week._")
        return "\n".join(lines)

    work_entries = [e for e in all_entries if e["category"] == "work"]
    personal_entries = [e for e in all_entries if e["category"] == "personal"]

    lines.append(f"**{len(all_entries)} notes across {days_active} days** "
                 f"({len(work_entries)} work, {len(personal_entries)} personal)\n")

    # Day-by-day breakdown
    for i in range(7):
        d = start + timedelta(days=i)
        day_entries = _load_day(d.isoformat())
        if not day_entries:
            continue
        day_name = d.strftime("%A %b %d")
        lines.append(f"## {day_name}\n")
        for cat, label in [("work", "Work"), ("personal", "Personal")]:
            cat_entries = [e for e in day_entries if e["category"] == cat]
            if not cat_entries:
                continue
            lines.append(f"### {label}\n")
            for e in cat_entries:
                tag_str = " " + " ".join(f"`#{t}`" for t in e["tags"]) if e.get("tags") else ""
                lines.append(f"- **{e['time']}** — {e['text']}{tag_str}")
            lines.append("")

    # Weekly tag overview
    all_tags: dict[str, int] = {}
    for e in all_entries:
        for t in e.get("tags", []):
            all_tags[t] = all_tags.get(t, 0) + 1
    if all_tags:
        lines.append("## Top Tags\n")
        for tag, count in sorted(all_tags.items(), key=lambda x: -x[1])[:15]:
            lines.append(f"- #{tag} ({count})")
        lines.append("")

    lines.append("---")
    lines.append(f"_Week of {week_label}_")
    return "\n".join(lines)


def register_daily_notes(mcp: FastMCP):
    """Register all daily notes tools on the MCP server."""

    @mcp.tool()
    def add_work_note(text: str, tags: str = "", note_date: str = "") -> str:
        """
        Save a work note for today (or a specific date).

        Args:
            text:      The note content.
            tags:      Comma-separated tags (e.g. 'varonis,meeting,deploy').
            note_date: Optional YYYY-MM-DD. Defaults to today.
        """
        return _add_entry(text, "work", tags, note_date)

    @mcp.tool()
    def add_personal_note(text: str, tags: str = "", note_date: str = "") -> str:
        """
        Save a personal note for today (or a specific date).

        Args:
            text:      The note content.
            tags:      Comma-separated tags (e.g. 'health,errand,idea').
            note_date: Optional YYYY-MM-DD. Defaults to today.
        """
        return _add_entry(text, "personal", tags, note_date)

    @mcp.tool()
    def daily_summary(note_date: str = "") -> str:
        """
        Generate a Markdown summary of all notes for a given day.
        Groups by work/personal, shows timestamps and tags.

        Args:
            note_date: YYYY-MM-DD. Defaults to today.
        """
        return _build_daily_summary(note_date)

    @mcp.tool()
    def weekly_notes_summary(weeks_back: int = 0) -> str:
        """
        Generate a Markdown summary of all notes for a full week (Mon–Sun).
        Shows day-by-day breakdown, work/personal split, and tag overview.

        Args:
            weeks_back: 0 = current week, 1 = last week, etc.
        """
        return _build_weekly_summary(weeks_back)

    @mcp.tool()
    def list_daily_notes(note_date: str = "", category: str = "") -> str:
        """
        List notes for a given day, optionally filtered by category.

        Args:
            note_date: YYYY-MM-DD. Defaults to today.
            category:  Filter to 'work' or 'personal'. Empty = all.
        """
        entries = _load_day(note_date or date.today().isoformat())
        if category:
            entries = [e for e in entries if e["category"] == category]
        if not entries:
            return "No notes found."
        lines = []
        for e in entries:
            tag_str = " " + " ".join(f"#{t}" for t in e["tags"]) if e.get("tags") else ""
            lines.append(f"- [{e['category']}] **{e['time']}** (#{e['id']}) — {e['text']}{tag_str}")
        return "\n".join(lines)

    @mcp.tool()
    def delete_daily_note(note_id: int, note_date: str = "") -> str:
        """
        Delete a note by its ID for a given day.

        Args:
            note_id:   The note ID to delete.
            note_date: YYYY-MM-DD. Defaults to today.
        """
        d = note_date or date.today().isoformat()
        entries = _load_day(d)
        before = len(entries)
        entries = [e for e in entries if e["id"] != note_id]
        if len(entries) == before:
            return f"No note #{note_id} found on {d}."
        _save_day(entries, d)
        return f"Deleted note #{note_id} from {d}."

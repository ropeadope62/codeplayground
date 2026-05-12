"""
daily_digest.py — End-of-day activity summary generator.

Aggregates daily notes, journal entries, focus sessions, and reminders
into a plain-text summary file stored in notes/digests/YYYY-MM-DD.txt.

The daily briefing reads the previous day's digest to provide continuity,
and the weekly review reads the week's digests for a richer retrospective.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import json
from pathlib import Path
from datetime import datetime, date, timedelta
from mcp.server import FastMCP

_BASE = Path(__file__).resolve().parent.parent
DIGEST_DIR = _BASE / "notes" / "digests"
DIGEST_DIR.mkdir(parents=True, exist_ok=True)

# Paths to other data stores
DAILY_NOTES_DIR = _BASE / "notes" / "daily"
NOTES_FILE = _BASE / "notes" / "notes.json"
REMINDERS_FILE = _BASE / "notes" / "reminders.json"
FOCUS_LOG = _BASE / "logs" / "focus_log.json"
JOURNAL_DIR = Path("~/Documents/work/journal").expanduser()


def _load_json(path: Path) -> list:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _digest_path(d: str = "") -> Path:
    if not d:
        d = date.today().isoformat()
    return DIGEST_DIR / f"{d}.txt"


def _build_digest(target_date: str = "") -> str:
    """Build a plain-text daily activity summary for a given date."""
    d = target_date or date.today().isoformat()
    try:
        day_name = datetime.strptime(d, "%Y-%m-%d").strftime("%A, %B %d, %Y")
    except ValueError:
        day_name = d

    sections: list[str] = []
    sections.append(f"DAILY ACTIVITY DIGEST — {day_name}")
    sections.append("=" * 50)

    # ── Daily notes (work + personal) ────────────────────────
    daily_notes_file = DAILY_NOTES_DIR / f"{d}.json"
    daily_entries = _load_json(daily_notes_file)

    if daily_entries:
        work_notes = [e for e in daily_entries if e.get("category") == "work"]
        personal_notes = [e for e in daily_entries if e.get("category") == "personal"]

        if work_notes:
            sections.append("")
            sections.append("WORK NOTES:")
            for e in work_notes:
                tags = " ".join(f"#{t}" for t in e.get("tags", []))
                tag_str = f" [{tags}]" if tags else ""
                sections.append(f"  {e.get('time', '')} - {e['text']}{tag_str}")

        if personal_notes:
            sections.append("")
            sections.append("PERSONAL NOTES:")
            for e in personal_notes:
                tags = " ".join(f"#{t}" for t in e.get("tags", []))
                tag_str = f" [{tags}]" if tags else ""
                sections.append(f"  {e.get('time', '')} - {e['text']}{tag_str}")
    else:
        sections.append("")
        sections.append("NOTES: None recorded")

    # ── Journal entries ──────────────────────────────────────
    journal_file = JOURNAL_DIR / f"{d}.md"
    if journal_file.exists():
        content = journal_file.read_text(encoding="utf-8", errors="ignore")
        entries = []
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("- **") and "** —" in line:
                # Strip markdown bold formatting for plain text
                clean = line.replace("- **", "").replace("**", "").replace(" —", " -")
                # Strip tag backticks
                import re
                clean = re.sub(r"`#([^`]+)`", r"#\1", clean)
                entries.append(f"  {clean}")

        if entries:
            sections.append("")
            sections.append("JOURNAL ENTRIES:")
            sections.extend(entries)

    # ── Focus sessions ───────────────────────────────────────
    focus_entries = _load_json(FOCUS_LOG)
    day_focus = [e for e in focus_entries if e.get("date") == d]

    if day_focus:
        total_min = sum(e.get("actual_min", 0) for e in day_focus)
        completed = sum(1 for e in day_focus if e.get("completed"))
        sections.append("")
        sections.append(f"FOCUS SESSIONS: {len(day_focus)} sessions, {round(total_min)} min total, {completed} completed")
        for e in day_focus:
            status = "completed" if e.get("completed") else "stopped early"
            sections.append(f"  - {e.get('label', 'unnamed')} ({round(e.get('actual_min', 0))} min, {status})")

    # ── Reminders that were due ──────────────────────────────
    all_reminders = _load_json(REMINDERS_FILE)
    due_today = [
        r for r in all_reminders
        if r.get("due", "")[:10] == d
    ]
    dismissed_today = [r for r in due_today if r.get("done")]
    still_pending = [r for r in due_today if not r.get("done")]

    if due_today:
        sections.append("")
        sections.append("REMINDERS:")
        for r in dismissed_today:
            sections.append(f"  [DONE] {r['title']}")
        for r in still_pending:
            sections.append(f"  [PENDING] {r['title']}")

    # ── Persistent notes added today ─────────────────────────
    all_notes = _load_json(NOTES_FILE)
    today_notes = [
        n for n in all_notes
        if n.get("date", n.get("created", ""))[:10] == d
    ]
    if today_notes:
        sections.append("")
        sections.append("NOTES ADDED:")
        for n in today_notes:
            tag = n.get("tag", "")
            tag_str = f" [{tag}]" if tag else ""
            sections.append(f"  {n['text']}{tag_str}")

    # ── Summary footer ───────────────────────────────────────
    sections.append("")
    sections.append("-" * 50)
    sections.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    return "\n".join(sections)


def read_digest(target_date: str = "") -> str:
    """Read a previously saved daily digest. Returns empty string if none exists."""
    path = _digest_path(target_date)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def read_digest_range(days_back: int = 7) -> list[dict]:
    """Read digests for the last N days. Returns list of {date, content}."""
    results = []
    today = date.today()
    for i in range(days_back):
        d = (today - timedelta(days=i)).isoformat()
        content = read_digest(d)
        if content:
            results.append({"date": d, "content": content})
    return results


def register_daily_digest(mcp: FastMCP, context_memory=None):
    """Register daily digest tools on the MCP server."""

    @mcp.tool()
    def generate_daily_digest(target_date: str = "") -> str:
        """
        Generate and save a daily activity summary to a .txt file.

        Aggregates the day's work notes, personal notes, journal entries,
        focus sessions, and reminders into a single plain-text digest file
        stored in notes/digests/YYYY-MM-DD.txt.

        Also indexes the day's activity into semantic memory (ChromaDB)
        so it can be recalled via natural language search later.

        Call this at end of day or anytime to snapshot the day's activity.
        The daily briefing automatically reads yesterday's digest for continuity.

        Args:
            target_date: YYYY-MM-DD. Defaults to today.
        """
        d = target_date or date.today().isoformat()
        content = _build_digest(d)
        path = _digest_path(d)
        path.write_text(content, encoding="utf-8")
        line_count = len(content.splitlines())

        # Index into semantic memory
        indexed = 0
        if context_memory:
            try:
                result = context_memory.index_day(d)
                indexed = result.get("entries", 0)
            except Exception:
                pass

        return json.dumps({
            "action": "digest_saved",
            "date": d,
            "path": str(path),
            "lines": line_count,
            "indexed_to_memory": indexed,
        }, indent=2)

    @mcp.tool()
    def read_daily_digest(target_date: str = "") -> str:
        """
        Read a previously saved daily activity digest.

        Args:
            target_date: YYYY-MM-DD. Defaults to today.
        """
        d = target_date or date.today().isoformat()
        content = read_digest(d)
        if not content:
            return json.dumps({"date": d, "message": "No digest found for this date."})
        return content

    @mcp.tool()
    def list_daily_digests(days_back: int = 14) -> str:
        """
        List available daily digests for the last N days.

        Args:
            days_back: How many days to look back (default 14).
        """
        today = date.today()
        available = []
        for i in range(days_back):
            d = (today - timedelta(days=i)).isoformat()
            path = _digest_path(d)
            if path.exists():
                size = path.stat().st_size
                available.append({"date": d, "size_bytes": size})
        return json.dumps(available, indent=2)

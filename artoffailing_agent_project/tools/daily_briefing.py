"""
daily_briefing.py — blacksun-agent tool
Composes Gmail + Google Calendar into a morning digest.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import json
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from mcp.server import FastMCP

REMINDERS_FILE = Path(__file__).resolve().parent.parent / "notes" / "reminders.json"


def _load_due_reminders() -> list[dict]:
    """Return reminders that are due today or overdue (not dismissed)."""
    if not REMINDERS_FILE.exists():
        return []
    reminders = json.loads(REMINDERS_FILE.read_text(encoding="utf-8"))
    today_str = date.today().strftime("%Y-%m-%d")
    return [
        r for r in reminders
        if not r.get("done") and r["due"][:10] <= today_str
    ]

try:
    from zoneinfo import ZoneInfo
    import tzdata  # noqa: F401 — ensures IANA db is available on Windows
    TZ = ZoneInfo("America/Toronto")
except Exception:
    # Fallback: UTC offset for ET (no DST awareness, but functional)
    TZ = timezone.utc


def _fmt_time(iso: str) -> str:
    """Parse an ISO datetime string and return HH:MM."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ)
        return dt.strftime("%H:%M")
    except Exception:
        return iso


def register_daily_briefing(mcp: FastMCP, gmail_client=None, gcal_client=None, context_memory=None):
    """
    Register the daily_briefing tool.

    gmail_client    — your existing Gmail MCP/wrapper (must expose .list_messages, .get_thread)
    gcal_client     — your existing GCal MCP/wrapper (must expose .list_events)
    context_memory  — ContextMemory instance for semantic recall

    If clients are None the tool returns a stub — useful for testing.
    """

    @mcp.tool()
    def daily_briefing(
        max_emails: int = 5,
        max_events: int = 8,
        include_tomorrow: bool = False,
    ) -> str:
        """
        Generate a morning briefing as Markdown.

        Pulls:
          - Today's Google Calendar events (optionally tomorrow's too)
          - Recent unread Gmail threads (subject + sender + snippet)

        Args:
            max_emails:       Max unread email threads to surface (default 5)
            max_events:       Max calendar events to list (default 8)
            include_tomorrow: Also include tomorrow's events (default False)
        """
        today = date.today()
        now = datetime.now(tz=TZ)
        lines: list[str] = []

        # Resolve lazy factories (callables) into actual client instances
        gcal = gcal_client() if callable(gcal_client) else gcal_client
        gmail = gmail_client() if callable(gmail_client) else gmail_client

        # ── Header ──────────────────────────────────────────────
        lines.append(f"# Daily briefing — {today.strftime('%A, %B %#d')}")
        lines.append(f"_Generated at {now.strftime('%H:%M')} ET_\n")

        # ── Calendar ─────────────────────────────────────────────
        lines.append("## Calendar\n")

        if gcal:
            try:
                if include_tomorrow:
                    events = gcal.list_events(days_ahead=2, max_results=max_events)
                else:
                    events = gcal.get_todays_events()[:max_events]

                if not events:
                    lines.append("_No events today._\n")
                else:
                    for ev in events:
                        start_raw = ev.get("start", "")
                        is_all_day = ev.get("is_all_day", False)
                        time_str = "all-day" if is_all_day else _fmt_time(start_raw)
                        title = ev.get("summary", "(no title)")
                        # Flag if happening soon (within 30 min)
                        flag = ""
                        if not is_all_day:
                            try:
                                ev_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00")).astimezone(TZ)
                                mins_away = (ev_dt - now).total_seconds() / 60
                                if 0 <= mins_away <= 30:
                                    flag = " ⬅ soon"
                            except Exception:
                                pass
                        lines.append(f"- `{time_str}` {title}{flag}")
            except Exception as e:
                lines.append(f"_Could not fetch calendar events: {e}_")
        else:
            lines.append("_Calendar not connected._")

        lines.append("")

        # ── Email ─────────────────────────────────────────────────
        lines.append("## Unread email\n")

        if gmail:
            try:
                result = gmail.list_messages(
                    query="is:unread",
                    max_results=max_emails,
                )
                threads = result.get("messages", []) if isinstance(result, dict) else result
                if not threads:
                    lines.append("_Inbox zero — nothing unread._\n")
                else:
                    for t in threads:
                        sender = t.get("from", "Unknown")
                        subject = t.get("subject", "(no subject)")
                        snippet = t.get("snippet", "")[:80]
                        lines.append(f"- **{sender}** — {subject}")
                        if snippet:
                            lines.append(f"  _{snippet}…_")
            except Exception as e:
                lines.append(f"_Could not fetch email: {e}_")
        else:
            lines.append("_Gmail not connected._")

        lines.append("")

        # ── Pending notes ────────────────────────────────────────
        notes_file = __import__("pathlib").Path(__file__).resolve().parent.parent / "notes" / "notes.json"
        if notes_file.exists():
            notes = json.loads(notes_file.read_text())
            todos = [n for n in notes if n.get("tag") == "todo"]
            followups = [n for n in notes if n.get("tag") == "followup"]
            if todos or followups:
                lines.append("## Pending from notes\n")
                for n in (todos + followups)[:6]:
                    tag = n["tag"]
                    lines.append(f"- [{tag}] {n['text']}")
                lines.append("")
        # ── Reminders ────────────────────────────────────────
        due = _load_due_reminders()
        if due:
            lines.append("## Reminders\n")
            for r in due:
                overdue = " ⚠ OVERDUE" if r["due"] < datetime.now().strftime("%Y-%m-%d %H:%M") else ""
                line = f"- `{r['due']}` {r['title']}{overdue}"
                if r.get("notes"):
                    line += f" — _{r['notes']}_"
                lines.append(line)
            lines.append("")

        # ── Yesterday's digest ───────────────────────────────
        from tools.daily_digest import read_digest
        yesterday = (today - timedelta(days=1)).isoformat()
        yesterday_digest = read_digest(yesterday)
        if yesterday_digest:
            lines.append("## Yesterday's summary\n")
            lines.append(f"_{yesterday}_\n")
            # Include the digest content as a blockquote for readability
            for dline in yesterday_digest.splitlines():
                if dline.strip():
                    lines.append(f"> {dline}")
                else:
                    lines.append(">")
            lines.append("")

        # ── Relevant context from memory ─────────────────────
        if context_memory:
            try:
                # Pull context related to today's calendar events
                event_topics = []
                if gcal:
                    try:
                        today_events = gcal.get_todays_events()[:5]
                        event_topics = [
                            ev.get("summary", "")
                            for ev in today_events
                            if ev.get("summary")
                        ]
                    except Exception:
                        pass

                # Search for context related to today's meetings
                context_lines = []
                for topic in event_topics:
                    ctx = context_memory.get_relevant_context(topic, days_back=14, n_results=3)
                    if ctx:
                        context_lines.append(f"**{topic}:**")
                        context_lines.append(ctx)

                # Also pull general recent activity context
                general_ctx = context_memory.get_relevant_context(
                    "recent work activity tasks and follow-ups",
                    days_back=3,
                    n_results=5,
                )
                if general_ctx:
                    context_lines.append("**Recent activity:**")
                    context_lines.append(general_ctx)

                if context_lines:
                    lines.append("## Context from memory\n")
                    lines.append("_Relevant activity recalled from semantic memory:_\n")
                    lines.extend(context_lines)
                    lines.append("")
            except Exception:
                pass

        # ── Footer ───────────────────────────────────────────────
        lines.append("---")
        lines.append(f"_Have a great day._")

        return "\n".join(lines)

    @mcp.tool()
    def briefing_to_file(output_path: str = str(Path(__file__).resolve().parent.parent / "notes" / "daily_briefing.md")) -> str:
        """
        Run daily_briefing() and write the result to a Markdown file.
        Useful for cron / scheduled morning automation.
        """
        from pathlib import Path
        md = daily_briefing()
        dest = Path(output_path).expanduser()
        dest.write_text(md)
        return f"Briefing written to {dest}"

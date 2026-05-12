"""
weekly_review.py — blacksun-agent tool
Pulls notes + focus log + calendar into a structured Markdown retrospective.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import json
from datetime import datetime, date, timedelta
from pathlib import Path
from mcp.server import FastMCP

NOTES_FILE = Path(__file__).resolve().parent.parent / "notes" / "notes.json"
FOCUS_LOG = Path(__file__).resolve().parent.parent / "logs" / "focus_log.json"
REMINDERS_FILE = Path(__file__).resolve().parent.parent / "notes" / "reminders.json"


def _load_json(path: Path) -> list:
    if not path.exists():
        return []
    return json.loads(path.read_text())


def register_weekly_review(mcp: FastMCP, gcal_client=None, context_memory=None):

    @mcp.tool()
    def weekly_review(
        weeks_back: int = 0,
        output_path: str = "",
    ) -> str:
        """
        Generate a structured weekly retrospective as Markdown.

        Includes:
          - Focus sessions (hours worked, by project)
          - Notes captured this week (by tag)
          - Completed calendar events
          - Auto-generated reflection prompts

        Args:
            weeks_back:  0 = current week, 1 = last week, etc.
            output_path: If provided, write to this file instead of returning string
        """
        today = date.today()
        # Week runs Mon–Sun
        start_of_week = today - timedelta(days=today.weekday() + weeks_back * 7)
        end_of_week = start_of_week + timedelta(days=6)

        week_label = (
            f"{start_of_week.strftime('%b %#d')}–{end_of_week.strftime('%b %#d, %Y')}"
        )

        lines: list[str] = []
        lines.append(f"# Weekly review — {week_label}\n")
        lines.append(f"_Generated {today.strftime('%Y-%m-%d')}_\n")

        # ── Focus log ────────────────────────────────────────────
        focus_entries = _load_json(FOCUS_LOG)
        week_focus = [
            e for e in focus_entries
            if start_of_week.isoformat() <= e["date"] <= end_of_week.isoformat()
        ]

        lines.append("## Focus sessions\n")
        if not week_focus:
            lines.append("_No focus sessions logged this week._\n")
        else:
            total_min = sum(e["actual_min"] for e in week_focus)
            completed = sum(1 for e in week_focus if e["completed"])
            lines.append(
                f"**{len(week_focus)} sessions · "
                f"{round(total_min / 60, 1)} hrs · "
                f"{completed} completed**\n"
            )
            # Group by label for a project breakdown
            by_label: dict[str, float] = {}
            for e in week_focus:
                by_label[e["label"]] = by_label.get(e["label"], 0) + e["actual_min"]
            for label, mins in sorted(by_label.items(), key=lambda x: -x[1]):
                hours = round(mins / 60, 1)
                lines.append(f"- {label} — {hours} hr{'s' if hours != 1 else ''}")
            lines.append("")

        # ── Notes ────────────────────────────────────────────────
        all_notes = _load_json(NOTES_FILE)
        week_notes = [
            n for n in all_notes
            if start_of_week.isoformat() <= n.get("date", n.get("created", "")) <= end_of_week.isoformat()
        ]

        # ── Daily digests ────────────────────────────────────────
        from tools.daily_digest import read_digest
        digest_days = []
        for i in range(7):
            d = (start_of_week + timedelta(days=i)).isoformat()
            content = read_digest(d)
            if content:
                digest_days.append((d, content))

        if digest_days:
            lines.append("## Daily activity digests\n")
            lines.append(f"_Digests available for {len(digest_days)} of 7 days_\n")
            for d, content in digest_days:
                try:
                    day_name = datetime.strptime(d, "%Y-%m-%d").strftime("%A %b %#d")
                except ValueError:
                    day_name = d
                lines.append(f"### {day_name}\n")
                lines.append("```")
                lines.append(content)
                lines.append("```\n")

        # ── Semantic themes from memory ──────────────────────────
        if context_memory:
            try:
                theme_queries = [
                    ("Work themes", "key work tasks projects meetings deliverables"),
                    ("Follow-ups", "follow up action items pending blocked waiting"),
                    ("Learning & insights", "learned discovered insight idea realized"),
                ]
                theme_lines = []
                for label, query in theme_queries:
                    ctx = context_memory.get_relevant_context(
                        query,
                        days_back=7,
                        n_results=5,
                    )
                    if ctx:
                        theme_lines.append(f"### {label}\n")
                        theme_lines.append(ctx)
                        theme_lines.append("")

                if theme_lines:
                    lines.append("## Recurring themes (from memory)\n")
                    lines.append("_Semantic search across this week's indexed activity:_\n")
                    lines.extend(theme_lines)
            except Exception:
                pass

        lines.append("## Notes captured\n")
        if not week_notes:
            lines.append("_No notes this week._\n")
        else:
            tag_order = ["idea", "insight", "todo", "followup", "ref"]
            tag_labels = {
                "idea": "Ideas", "insight": "Insights",
                "todo": "To-dos", "followup": "Follow-ups", "ref": "References"
            }
            grouped: dict[str, list] = {t: [] for t in tag_order}
            for n in week_notes:
                grouped.get(n.get("tag", "ref"), grouped["ref"]).append(n)

            for tag in tag_order:
                items = grouped[tag]
                if not items:
                    continue
                lines.append(f"### {tag_labels[tag]}\n")
                for n in items:
                    lines.append(f"- {n['text']}")
                lines.append("")

        # ── Calendar ─────────────────────────────────────────────
        lines.append("## Events this week\n")
        if gcal_client:
            try:
                gcal = gcal_client() if callable(gcal_client) else gcal_client
                start_iso = datetime.combine(start_of_week, datetime.min.time()).isoformat() + "Z"
                end_iso = datetime.combine(end_of_week + timedelta(days=1), datetime.min.time()).isoformat() + "Z"
                events = gcal.list_events_range(
                    time_min=start_iso,
                    time_max=end_iso,
                    max_results=30,
                )
                if not events:
                    lines.append("_No calendar events found._\n")
                else:
                    for ev in events:
                        start_raw = ev.get("start", "")
                        try:
                            ev_date = datetime.fromisoformat(
                                start_raw.replace("Z", "+00:00")
                            ).strftime("%a %#d")
                        except Exception:
                            ev_date = start_raw[:10]
                        lines.append(f"- {ev_date} — {ev.get('summary', '(no title)')}")
                    lines.append("")
            except Exception as e:
                lines.append(f"_Could not fetch calendar: {e}_\n")
        else:
            lines.append("_Calendar client not connected — pass gcal_client to register_weekly_review()._\n")

        # ── Carry-forward todos ──────────────────────────────────
        open_todos = [
            n for n in all_notes
            if n.get("tag") in ("todo", "followup")
            and n.get("date", n.get("created", "")) < start_of_week.isoformat()
        ]
        if open_todos:
            lines.append("## Carry-forward items\n")
            lines.append("_Open todos/follow-ups from before this week:_\n")
            for n in open_todos[:8]:
                    lines.append(f"- [{n['tag']}] {n['text']} _(added {n.get('date', n.get('created', ''))})_")
            lines.append("")

        # ── Reminders due this week ──────────────────────────
        if REMINDERS_FILE.exists():
            all_reminders = _load_json(REMINDERS_FILE)
            week_reminders = [
                r for r in all_reminders
                if not r.get("done")
                and r["due"][:10] <= end_of_week.isoformat()
            ]
            if week_reminders:
                lines.append("## Reminders\n")
                overdue_label = start_of_week.isoformat()
                for r in week_reminders:
                    is_overdue = r["due"][:10] < start_of_week.isoformat()
                    flag = " ⚠ OVERDUE" if is_overdue else ""
                    line = f"- `{r['due']}` {r['title']}{flag}"
                    if r.get("notes"):
                        line += f" — _{r['notes']}_"
                    lines.append(line)
                lines.append("")

        # ── Reflection prompts ───────────────────────────────────
        lines.append("## Reflection\n")
        lines.append("_Answer these before closing the week:_\n")
        prompts = [
            "What's the one thing I shipped or moved forward this week?",
            "What kept me from doing my best work?",
            "What should carry forward as the top priority next week?",
            "What did I learn that's worth writing about?",
        ]
        for p in prompts:
            lines.append(f"- {p}")
            lines.append(f"  > ")
        lines.append("")
        lines.append("---")
        lines.append(f"_Week of {week_label}_")

        md = "\n".join(lines)

        if output_path:
            dest = Path(output_path).expanduser()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(md)
            return f"Weekly review written to {dest}"

        return md

    @mcp.tool()
    def weekly_review_to_file(weeks_back: int = 0) -> str:
        """
        Generate weekly review and save to ~/notes/weekly/YYYY-WNN.md automatically.
        """
        today = date.today()
        year, week, _ = (today - timedelta(weeks=weeks_back)).isocalendar()
        path = f"~/notes/weekly/{year}-W{week:02d}.md"
        return weekly_review(weeks_back=weeks_back, output_path=path)

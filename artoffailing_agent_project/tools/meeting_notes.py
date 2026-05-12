"""
Meeting notes — structured templates for 1:1s and meetings.

Stores notes as dated markdown files in ~/Documents/work/meetings/.
Supports 1:1 format (with recurring context) and general meeting format.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import os
import re
from pathlib import Path
from datetime import datetime


DEFAULT_WORK_PATH = os.path.expanduser("~/Documents/work")


class MeetingNotes:
    """Structured meeting and 1:1 note management."""

    def __init__(self, base_path: str = DEFAULT_WORK_PATH):
        self.meetings_dir = Path(base_path) / "meetings"
        self.meetings_dir.mkdir(parents=True, exist_ok=True)

    def _slugify(self, text: str) -> str:
        slug = text.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        return slug.strip("-")[:60]

    def create_one_on_one(
        self,
        person: str,
        topics: list[str] | None = None,
        action_items: list[str] | None = None,
        notes: str = "",
        date: str = "",
    ) -> dict:
        """Create a 1:1 meeting note.

        Args:
            person: Who the 1:1 is with (e.g. 'Hadi', 'Manager Name').
            topics: Discussion topics/agenda items.
            action_items: Any action items coming out of the meeting.
            notes: Free-form notes from the meeting.
            date: YYYY-MM-DD. Empty = today.
        """
        date_str = date or datetime.now().strftime("%Y-%m-%d")
        slug = self._slugify(f"1on1-{person}")
        filename = f"{date_str}-{slug}.md"
        filepath = self.meetings_dir / filename

        lines = [
            f"# 1:1 with {person}",
            f"**Date:** {date_str}",
            f"**Type:** 1:1",
            "",
        ]

        # Check for previous 1:1s with this person
        previous = self._find_previous_meetings(person)
        if previous:
            last = previous[0]
            lines.append(f"**Previous 1:1:** [{last['filename']}]({last['filename']})")
            lines.append("")

        lines.append("## Agenda")
        if topics:
            for topic in topics:
                lines.append(f"- [ ] {topic}")
        else:
            lines.append("- [ ] ")
        lines.append("")

        lines.append("## Discussion Notes")
        if notes:
            lines.append(notes)
        else:
            lines.append("_Notes from the conversation..._")
        lines.append("")

        lines.append("## Action Items")
        if action_items:
            for item in action_items:
                lines.append(f"- [ ] {item}")
        else:
            lines.append("- [ ] ")
        lines.append("")

        lines.append("## Follow-up")
        lines.append("_Items to bring to the next 1:1..._")
        lines.append("")

        filepath.write_text("\n".join(lines), encoding="utf-8")

        return {
            "action": "created",
            "type": "1:1",
            "person": person,
            "date": date_str,
            "filename": filename,
            "path": str(filepath),
            "previous_meetings": len(previous),
        }

    def create_meeting_note(
        self,
        title: str,
        attendees: list[str] | None = None,
        topics: list[str] | None = None,
        decisions: list[str] | None = None,
        action_items: list[str] | None = None,
        notes: str = "",
        date: str = "",
    ) -> dict:
        """Create a general meeting note.

        Args:
            title: Meeting title (e.g. 'Varonis SaaS Migration Sync').
            attendees: List of attendee names.
            topics: Agenda/discussion topics.
            decisions: Key decisions made during the meeting.
            action_items: Action items with owners if known.
            notes: Free-form notes.
            date: YYYY-MM-DD. Empty = today.
        """
        date_str = date or datetime.now().strftime("%Y-%m-%d")
        slug = self._slugify(title)
        filename = f"{date_str}-{slug}.md"
        filepath = self.meetings_dir / filename

        lines = [
            f"# {title}",
            f"**Date:** {date_str}",
            f"**Type:** Meeting",
        ]

        if attendees:
            lines.append(f"**Attendees:** {', '.join(attendees)}")
        lines.append("")

        lines.append("## Agenda")
        if topics:
            for topic in topics:
                lines.append(f"- [ ] {topic}")
        else:
            lines.append("- [ ] ")
        lines.append("")

        lines.append("## Discussion Notes")
        if notes:
            lines.append(notes)
        else:
            lines.append("_Notes from the meeting..._")
        lines.append("")

        if decisions:
            lines.append("## Decisions")
            for decision in decisions:
                lines.append(f"- {decision}")
            lines.append("")

        lines.append("## Action Items")
        if action_items:
            for item in action_items:
                lines.append(f"- [ ] {item}")
        else:
            lines.append("- [ ] ")
        lines.append("")

        filepath.write_text("\n".join(lines), encoding="utf-8")

        return {
            "action": "created",
            "type": "meeting",
            "title": title,
            "date": date_str,
            "filename": filename,
            "path": str(filepath),
        }

    def add_to_meeting(self, filename: str, section: str, content: str) -> dict:
        """Append content to a specific section of an existing meeting note.

        Args:
            filename: Meeting note filename (partial match works).
            section: Section header to append to (e.g. 'Discussion Notes', 'Action Items').
            content: Text to append.
        """
        filepath = self._find_file(filename)
        text = filepath.read_text(encoding="utf-8")

        # Find the section and append before the next section
        section_pattern = f"## {section}"
        if section_pattern not in text:
            # Add the section at the end
            text = text.rstrip() + f"\n\n{section_pattern}\n{content}\n"
        else:
            # Find the section and the next section after it
            parts = text.split(section_pattern, 1)
            after_section = parts[1]

            # Find next ## header
            next_header = re.search(r"\n## ", after_section)
            if next_header:
                insert_point = next_header.start()
                after_section = after_section[:insert_point] + f"\n{content}" + after_section[insert_point:]
            else:
                after_section = after_section.rstrip() + f"\n{content}\n"

            text = parts[0] + section_pattern + after_section

        filepath.write_text(text, encoding="utf-8")

        return {
            "action": "updated",
            "filename": filepath.name,
            "section": section,
            "path": str(filepath),
        }

    def read_meeting(self, filename: str) -> dict:
        """Read a meeting note.

        Args:
            filename: Meeting filename (partial match works).
        """
        filepath = self._find_file(filename)
        content = filepath.read_text(encoding="utf-8")

        # Extract metadata
        person_match = re.search(r"# 1:1 with (.+)", content)
        title_match = re.search(r"# (.+)", content) if not person_match else None
        date_match = re.search(r"\*\*Date:\*\* (\d{4}-\d{2}-\d{2})", content)
        type_match = re.search(r"\*\*Type:\*\* (.+)", content)

        return {
            "filename": filepath.name,
            "title": person_match.group(0).strip("# ") if person_match else (title_match.group(1) if title_match else filepath.stem),
            "date": date_match.group(1) if date_match else filepath.name[:10],
            "type": type_match.group(1) if type_match else "unknown",
            "content": content,
            "path": str(filepath),
        }

    def list_meetings(self, days_back: int = 30, person: str = "") -> list[dict]:
        """List recent meeting notes.

        Args:
            days_back: How far back to look (default 30 days).
            person: Filter by person name (for 1:1s). Empty = all meetings.
        """
        results = []
        cutoff = datetime.now().timestamp() - (days_back * 86400)

        for filepath in sorted(self.meetings_dir.glob("*.md"), reverse=True):
            if filepath.stat().st_mtime < cutoff:
                continue

            content = filepath.read_text(encoding="utf-8", errors="ignore")

            if person and person.lower() not in content.lower():
                continue

            # Extract title from first heading
            title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
            title = title_match.group(1) if title_match else filepath.stem

            type_match = re.search(r"\*\*Type:\*\* (.+)", content)
            meeting_type = type_match.group(1) if type_match else "unknown"

            results.append({
                "filename": filepath.name,
                "title": title,
                "date": filepath.name[:10],
                "type": meeting_type,
            })

        return results

    def search_meetings(self, query: str, days_back: int = 90) -> list[dict]:
        """Search across all meeting notes.

        Args:
            query: Text to search for (case-insensitive).
            days_back: How far back to search.
        """
        query_lower = query.lower()
        results = []
        cutoff = datetime.now().timestamp() - (days_back * 86400)

        for filepath in sorted(self.meetings_dir.glob("*.md"), reverse=True):
            if filepath.stat().st_mtime < cutoff:
                continue

            content = filepath.read_text(encoding="utf-8", errors="ignore")
            if query_lower in content.lower():
                # Find matching lines for context
                matches = []
                for line in content.splitlines():
                    if query_lower in line.lower() and not line.startswith("#"):
                        matches.append(line.strip()[:200])
                        if len(matches) >= 3:
                            break

                title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
                results.append({
                    "filename": filepath.name,
                    "title": title_match.group(1) if title_match else filepath.stem,
                    "date": filepath.name[:10],
                    "matching_lines": matches,
                })

        return results

    def get_open_action_items(self, days_back: int = 30) -> list[dict]:
        """Find all unchecked action items across recent meeting notes.

        Args:
            days_back: How far back to look.
        """
        items = []
        cutoff = datetime.now().timestamp() - (days_back * 86400)

        for filepath in sorted(self.meetings_dir.glob("*.md"), reverse=True):
            if filepath.stat().st_mtime < cutoff:
                continue

            content = filepath.read_text(encoding="utf-8", errors="ignore")
            title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
            title = title_match.group(1) if title_match else filepath.stem

            for line in content.splitlines():
                line = line.strip()
                if line.startswith("- [ ]") and len(line) > 6:
                    item_text = line[5:].strip()
                    if item_text and item_text != "":
                        items.append({
                            "meeting": title,
                            "date": filepath.name[:10],
                            "action_item": item_text,
                            "filename": filepath.name,
                        })

        return items

    # ── Helpers ───────────────────────────────────────────────────────

    def _find_file(self, filename: str) -> Path:
        """Find a meeting note by filename (exact or partial match)."""
        exact = self.meetings_dir / filename
        if exact.exists():
            return exact

        for f in self.meetings_dir.glob("*.md"):
            if filename.lower() in f.name.lower():
                return f

        raise FileNotFoundError(f"Meeting note not found: {filename}")

    def _find_previous_meetings(self, person: str) -> list[dict]:
        """Find previous meeting notes mentioning a person."""
        person_lower = person.lower()
        results = []

        for filepath in sorted(self.meetings_dir.glob("*.md"), reverse=True):
            if person_lower in filepath.name.lower():
                results.append({"filename": filepath.name, "date": filepath.name[:10]})
                if len(results) >= 5:
                    break

        return results

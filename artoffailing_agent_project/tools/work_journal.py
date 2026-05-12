"""
Work journal — daily work logging with search and summaries.

Stores entries as dated markdown files in ~/Documents/work/journal/.
Each day is one file. Entries are timestamped and appendable throughout the day.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import os
import re
from pathlib import Path
from datetime import datetime, timedelta


DEFAULT_WORK_PATH = os.path.expanduser("~/Documents/work")


class WorkJournal:
    """Daily work journal stored as local markdown files."""

    def __init__(self, base_path: str = DEFAULT_WORK_PATH):
        self.journal_dir = Path(base_path) / "journal"
        self.journal_dir.mkdir(parents=True, exist_ok=True)

    def _date_path(self, date: str = "") -> Path:
        """Get the file path for a given date (YYYY-MM-DD). Empty = today."""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        return self.journal_dir / f"{date}.md"

    def log_entry(self, entry: str, tags: list[str] | None = None, date: str = "") -> dict:
        """Append a timestamped entry to today's journal.

        Args:
            entry: What you did, learned, or need to remember.
            tags: Optional tags (e.g. ['varonis', 'meeting', 'cyberark']).
            date: YYYY-MM-DD. Empty = today.

        Returns:
            Confirmation with file path and entry preview.
        """
        filepath = self._date_path(date)
        timestamp = datetime.now().strftime("%H:%M")
        date_str = date or datetime.now().strftime("%Y-%m-%d")

        # Create header if new file
        if not filepath.exists():
            day_name = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A, %B %d, %Y")
            header = f"# Work Journal — {day_name}\n\n"
            filepath.write_text(header, encoding="utf-8")

        # Format the entry
        tag_str = ""
        if tags:
            tag_str = " " + " ".join(f"`#{t}`" for t in tags)

        line = f"- **{timestamp}** — {entry}{tag_str}\n"

        with open(filepath, "a", encoding="utf-8") as f:
            f.write(line)

        return {
            "action": "logged",
            "date": date_str,
            "time": timestamp,
            "entry": entry[:100],
            "tags": tags or [],
            "path": str(filepath),
        }

    def read_journal(self, date: str = "") -> dict:
        """Read a day's journal entries.

        Args:
            date: YYYY-MM-DD. Empty = today.
        """
        filepath = self._date_path(date)
        date_str = date or datetime.now().strftime("%Y-%m-%d")

        if not filepath.exists():
            return {"date": date_str, "entries": [], "message": "No journal entries for this date."}

        content = filepath.read_text(encoding="utf-8")
        entries = []
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("- **") and "** —" in line:
                # Extract time and entry text
                match = re.match(r"- \*\*(\d{2}:\d{2})\*\* — (.+)", line)
                if match:
                    time_str = match.group(1)
                    text = match.group(2)
                    # Extract tags
                    tags = re.findall(r"`#([^`]+)`", text)
                    clean_text = re.sub(r"\s*`#[^`]+`", "", text).strip()
                    entries.append({"time": time_str, "entry": clean_text, "tags": tags})

        return {"date": date_str, "entries": entries, "entry_count": len(entries)}

    def read_journal_range(self, days_back: int = 7) -> list[dict]:
        """Read journal entries for the last N days.

        Args:
            days_back: How many days to look back (default 7).
        """
        results = []
        today = datetime.now()

        for i in range(days_back):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            journal = self.read_journal(date)
            if journal.get("entries"):
                results.append(journal)

        return results

    def search_journal(self, query: str, days_back: int = 90) -> list[dict]:
        """Search journal entries across multiple days.

        Args:
            query: Text to search for (case-insensitive).
            days_back: How far back to search (default 90 days).
        """
        query_lower = query.lower()
        results = []

        for filepath in sorted(self.journal_dir.glob("*.md"), reverse=True):
            # Check date range
            try:
                file_date = datetime.strptime(filepath.stem, "%Y-%m-%d")
                if (datetime.now() - file_date).days > days_back:
                    continue
            except ValueError:
                continue

            content = filepath.read_text(encoding="utf-8", errors="ignore")
            if query_lower in content.lower():
                matching_entries = []
                for line in content.splitlines():
                    if line.startswith("- **") and query_lower in line.lower():
                        matching_entries.append(line.strip())

                if matching_entries:
                    results.append({
                        "date": filepath.stem,
                        "matching_entries": matching_entries,
                    })

        return results

    def weekly_summary(self, weeks_back: int = 0) -> dict:
        """Get a summary of journal entries for a given week.

        Args:
            weeks_back: 0 = this week, 1 = last week, etc.
        """
        today = datetime.now()
        # Start of target week (Monday)
        start_of_week = today - timedelta(days=today.weekday() + (weeks_back * 7))
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_week = start_of_week + timedelta(days=6)

        all_entries = []
        all_tags = []
        days_with_entries = 0

        for i in range(7):
            date = (start_of_week + timedelta(days=i)).strftime("%Y-%m-%d")
            journal = self.read_journal(date)
            if journal.get("entries"):
                days_with_entries += 1
                for entry in journal["entries"]:
                    all_entries.append({"date": date, **entry})
                    all_tags.extend(entry.get("tags", []))

        # Tag frequency
        tag_counts = {}
        for tag in all_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "week_start": start_of_week.strftime("%Y-%m-%d"),
            "week_end": end_of_week.strftime("%Y-%m-%d"),
            "days_with_entries": days_with_entries,
            "total_entries": len(all_entries),
            "top_tags": top_tags,
            "entries": all_entries,
        }

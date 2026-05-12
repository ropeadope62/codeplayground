"""
notes_tool — blacksun-agent tool.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""
import json
import os
from datetime import datetime, date
from pathlib import Path
from mcp.server import FastMCP

_BASE = Path(__file__).resolve().parent.parent
NOTES_FILE = _BASE / "notes" / "notes.json"
NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)

TAGS = ["idea", "todo", "insight", "followup", "ref"]

def _load() -> list[dict]:
    if not NOTES_FILE.exists():
        return []
    return json.loads(NOTES_FILE.read_text())

def _save(notes: list[dict]):
    NOTES_FILE.write_text(json.dumps(notes, indent=2))

def _to_markdown(notes: list[dict]) -> str:
    groups: dict[str, list] = {t: [] for t in TAGS}
    for n in notes:
        groups.get(n["tag"], groups["ref"]).append(n)
    lines = [f"# Personal Notes", f"_Exported {date.today()}_\n"]
    for tag in TAGS:
        items = groups[tag]
        if not items:
            continue
        lines.append(f"## {tag.capitalize()}s\n")
        for n in items:
            lines.append(f"- **{n.get('created', '')}** — {n['text']}")
        lines.append("")
    return "\n".join(lines).strip()


def register_notes_tools(mcp: FastMCP):

    @mcp.tool()
    def add_note(text: str, tag: str = "idea") -> str:
        """
        Save a personal note. tag must be one of:
        idea | todo | insight | followup | ref
        """
        if tag not in TAGS:
            return f"Invalid tag '{tag}'. Choose from: {', '.join(TAGS)}"
        notes = _load()
        entry = {
            "id":   len(notes) + 1,
            "text": text.strip(),
            "tag":  tag,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
        notes.insert(0, entry)
        _save(notes)
        return f"Saved note #{entry['id']} [{tag}]: {text[:60]}"

    @mcp.tool()
    def list_notes(tag: str = "", query: str = "") -> str:
        """
        List saved notes. Optionally filter by tag or keyword query.
        Returns notes as formatted Markdown.
        """
        notes = _load()
        if tag:
            notes = [n for n in notes if n["tag"] == tag]
        if query:
            notes = [n for n in notes if query.lower() in n["text"].lower()]
        if not notes:
            return "No notes found."
        lines = []
        for n in notes:
            lines.append(f"- [{n['tag']}] **{n['date']}** (#{n['id']}) — {n['text']}")
        return "\n".join(lines)

    @mcp.tool()
    def delete_note(note_id: int) -> str:
        """Delete a note by its ID."""
        notes = _load()
        before = len(notes)
        notes = [n for n in notes if n["id"] != note_id]
        if len(notes) == before:
            return f"No note found with ID {note_id}"
        _save(notes)
        return f"Deleted note #{note_id}"

    @mcp.tool()
    def export_notes_markdown(output_path: str = "") -> str:
        """
        Export all notes as a curated Markdown file, grouped by tag.
        Optionally write to output_path; otherwise returns the Markdown string.
        """
        notes = _load()
        if not notes:
            return "No notes to export."
        md = _to_markdown(notes)
        if output_path:
            Path(output_path).expanduser().write_text(md)
            return f"Exported {len(notes)} notes to {output_path}"
        return md
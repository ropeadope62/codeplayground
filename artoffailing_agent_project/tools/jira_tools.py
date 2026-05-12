"""
Jira tools — generate formatted ticket content and comments.

Does NOT connect to Jira API. Generates copy-paste-ready text in Jira
markdown format, informed by work journal and meeting notes context.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import os
from pathlib import Path
from datetime import datetime

DEFAULT_WORK_PATH = os.path.expanduser("~/Documents/work")


class JiraTools:
    """Generate Jira-formatted ticket content and comments."""

    def __init__(self, base_path: str = DEFAULT_WORK_PATH):
        self.jira_dir = Path(base_path) / "jira" / "drafts"
        self.jira_dir.mkdir(parents=True, exist_ok=True)

    def create_ticket(
        self,
        title: str,
        description: str,
        scope: list[str] | None = None,
        exit_criteria: list[str] | None = None,
        ticket_type: str = "Story",
        priority: str = "Medium",
        labels: list[str] | None = None,
        components: list[str] | None = None,
        related_context: str = "",
    ) -> dict:
        """Generate a Jira ticket with full description, scope, and exit criteria.

        Args:
            title: Ticket summary/title.
            description: Detailed description of the work.
            scope: List of items that are in scope for this ticket.
            exit_criteria: List of acceptance criteria / definition of done.
            ticket_type: Story, Task, Bug, Epic, Sub-task.
            priority: Critical, High, Medium, Low.
            labels: Jira labels (e.g. ['varonis', 'sas-migration']).
            components: Jira components (e.g. ['Data Asset Protection']).
            related_context: Additional context from journal/meetings to inform the ticket.

        Returns:
            Dict with formatted Jira content ready to paste and a saved draft path.
        """
        # Build Jira-formatted description
        lines = []

        lines.append(f"h2. Description")
        lines.append(description)
        lines.append("")

        if related_context:
            lines.append(f"h2. Background Context")
            lines.append(related_context)
            lines.append("")

        if scope:
            lines.append("h2. Scope")
            for item in scope:
                lines.append(f"* {item}")
            lines.append("")

        if exit_criteria:
            lines.append("h2. Exit Criteria")
            for item in exit_criteria:
                lines.append(f"* (/) {item}")
            lines.append("")

        formatted_description = "\n".join(lines)

        # Build metadata block
        metadata = {
            "type": ticket_type,
            "priority": priority,
        }
        if labels:
            metadata["labels"] = labels
        if components:
            metadata["components"] = components

        # Save draft locally
        slug = title.lower().replace(" ", "-")[:50]
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_str}-{slug}.md"
        filepath = self.jira_dir / filename

        draft_content = [
            f"# Jira Ticket Draft",
            f"**Created:** {date_str}",
            f"**Type:** {ticket_type}",
            f"**Priority:** {priority}",
            "",
            f"## Title",
            title,
            "",
            f"## Description (Jira format — copy below this line)",
            "```",
            formatted_description,
            "```",
            "",
        ]

        if labels:
            draft_content.append(f"**Labels:** {', '.join(labels)}")
        if components:
            draft_content.append(f"**Components:** {', '.join(components)}")

        filepath.write_text("\n".join(draft_content), encoding="utf-8")

        return {
            "action": "ticket_drafted",
            "title": title,
            "type": ticket_type,
            "priority": priority,
            "filename": filename,
            "path": str(filepath),
            "jira_description": formatted_description,
            "metadata": metadata,
        }

    def format_comment(
        self,
        comment: str,
        status_update: str = "",
        blockers: list[str] | None = None,
        next_steps: list[str] | None = None,
        mentions: list[str] | None = None,
    ) -> dict:
        """Format a Jira issue comment in Jira wiki markup.

        Args:
            comment: Main comment text.
            status_update: Brief status (e.g. 'In Progress', 'Blocked', 'Testing').
            blockers: List of current blockers.
            next_steps: List of next steps / planned work.
            mentions: Jira usernames to @mention (e.g. ['jsmith', 'jdoe']).

        Returns:
            Dict with formatted comment text ready to paste.
        """
        lines = []

        if status_update:
            lines.append(f"*Status:* {status_update}")
            lines.append("")

        if mentions:
            mention_str = " ".join(f"[~{m}]" for m in mentions)
            lines.append(f"CC: {mention_str}")
            lines.append("")

        lines.append(comment)

        if blockers:
            lines.append("")
            lines.append("h3. Blockers")
            for blocker in blockers:
                lines.append(f"* (x) {blocker}")

        if next_steps:
            lines.append("")
            lines.append("h3. Next Steps")
            for step in next_steps:
                lines.append(f"* {step}")

        formatted = "\n".join(lines)

        return {
            "action": "comment_formatted",
            "formatted_comment": formatted,
        }

    def create_subtasks(self, parent_title: str, subtasks: list[dict]) -> dict:
        """Generate a set of subtask descriptions for a parent ticket.

        Args:
            parent_title: The parent ticket title for context.
            subtasks: List of dicts with 'title' and 'description' keys.

        Returns:
            Dict with formatted subtask list ready to create in Jira.
        """
        formatted = []
        for i, task in enumerate(subtasks, 1):
            title = task.get("title", f"Subtask {i}")
            desc = task.get("description", "")
            exit_criteria = task.get("exit_criteria", [])

            entry = {
                "index": i,
                "title": title,
                "jira_description": desc,
            }
            if exit_criteria:
                criteria_text = "\n".join(f"* (/) {c}" for c in exit_criteria)
                entry["jira_description"] += f"\n\nh3. Exit Criteria\n{criteria_text}"

            formatted.append(entry)

        # Save draft
        slug = parent_title.lower().replace(" ", "-")[:40]
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_str}-subtasks-{slug}.md"
        filepath = self.jira_dir / filename

        lines = [f"# Subtasks for: {parent_title}", f"**Created:** {date_str}", ""]
        for task in formatted:
            lines.append(f"## {task['index']}. {task['title']}")
            lines.append("```")
            lines.append(task["jira_description"])
            lines.append("```")
            lines.append("")

        filepath.write_text("\n".join(lines), encoding="utf-8")

        return {
            "action": "subtasks_drafted",
            "parent_title": parent_title,
            "count": len(formatted),
            "subtasks": formatted,
            "filename": filename,
            "path": str(filepath),
        }

    def list_drafts(self) -> list[dict]:
        """List saved Jira ticket drafts."""
        results = []
        for f in sorted(self.jira_dir.glob("*.md"), reverse=True):
            content = f.read_text(encoding="utf-8", errors="ignore")
            title_line = ""
            for line in content.splitlines():
                if line.startswith("## Title"):
                    # Next non-empty line is the title
                    idx = content.index(line) + len(line)
                    remaining = content[idx:].strip().splitlines()
                    if remaining:
                        title_line = remaining[0].strip()
                    break

            results.append({
                "filename": f.name,
                "title": title_line or f.stem,
                "date": f.name[:10],
                "size": f.stat().st_size,
            })

        return results

    def read_draft(self, filename: str) -> str:
        """Read a saved Jira ticket draft.

        Args:
            filename: Draft filename (partial match works).
        """
        for f in self.jira_dir.glob("*.md"):
            if filename.lower() in f.name.lower():
                return f.read_text(encoding="utf-8")

        raise FileNotFoundError(f"Jira draft not found: {filename}")

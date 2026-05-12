"""
Blog tools — Jekyll blog post management.

Generates properly formatted Jekyll markdown posts with front matter,
saves them to your blog's _posts or _drafts directory.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import re
import os
from pathlib import Path
from datetime import datetime, timezone


# Default path to your Jekyll blog repo — update this to match your setup
DEFAULT_BLOG_PATH = os.getenv(
    "BLOG_PATH",
    r"~/path/to/your/jekyll-blog",
)

# Common tags you use — the tool will suggest these
COMMON_TAGS = [
    "python", "discord", "automation", "ai", "llm", "devops",
    "homelab", "music", "projects", "security", "cloud",
    "minecraft", "tools", "cli", "api", "docker",
]

# Post categories
COMMON_CATEGORIES = [
    "projects", "tutorials", "thoughts", "tools", "life",
]


def _slugify(text: str) -> str:
    """Convert a title to a URL-friendly slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


class BlogTools:
    """Create and manage Jekyll blog drafts."""

    def __init__(self, blog_path: str = DEFAULT_BLOG_PATH):
        self.blog_path = Path(blog_path)

    def _ensure_dirs(self):
        """Make sure _posts and _drafts directories exist."""
        (self.blog_path / "_posts").mkdir(parents=True, exist_ok=True)
        (self.blog_path / "_drafts").mkdir(parents=True, exist_ok=True)

    def create_draft(
        self,
        title: str,
        tags: list[str] | None = None,
        categories: list[str] | None = None,
        excerpt: str = "",
        body: str = "",
        series: str = "",
        part: int | None = None,
    ) -> dict:
        """Create a new blog draft in the _drafts folder.

        Args:
            title: Post title.
            tags: List of tags (e.g. ['python', 'ai', 'tools']).
            categories: List of categories.
            excerpt: Short description for previews/SEO.
            body: Initial markdown body content. Can be empty to fill in later.
            series: If this is part of a series, the series name (e.g. 'Minecraft Bot').
            part: Part number if this is a series post.

        Returns:
            Dict with the file path and post metadata.
        """
        self._ensure_dirs()

        slug = _slugify(title)
        filename = f"{slug}.md"
        filepath = self.blog_path / "_drafts" / filename

        front_matter = self._build_front_matter(
            title=title,
            tags=tags or [],
            categories=categories or [],
            excerpt=excerpt,
            series=series,
            part=part,
        )

        content = f"{front_matter}\n{body}\n"
        filepath.write_text(content, encoding="utf-8")

        return {
            "action": "draft_created",
            "path": str(filepath),
            "filename": filename,
            "slug": slug,
            "title": title,
            "preview_cmd": "bundle exec jekyll serve --drafts",
        }

    def create_post(
        self,
        title: str,
        tags: list[str] | None = None,
        categories: list[str] | None = None,
        excerpt: str = "",
        body: str = "",
        series: str = "",
        part: int | None = None,
        date: str | None = None,
    ) -> dict:
        """Create a dated blog post in the _posts folder (ready to publish).

        Args:
            title: Post title.
            tags: List of tags.
            categories: List of categories.
            excerpt: Short description.
            body: Markdown body content.
            series: Series name if applicable.
            part: Part number if series.
            date: Publish date as YYYY-MM-DD. Defaults to today.

        Returns:
            Dict with the file path and post metadata.
        """
        self._ensure_dirs()

        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        slug = _slugify(title)
        filename = f"{date}-{slug}.md"
        filepath = self.blog_path / "_posts" / filename

        front_matter = self._build_front_matter(
            title=title,
            date=date,
            tags=tags or [],
            categories=categories or [],
            excerpt=excerpt,
            series=series,
            part=part,
        )

        content = f"{front_matter}\n{body}\n"
        filepath.write_text(content, encoding="utf-8")

        return {
            "action": "post_created",
            "path": str(filepath),
            "filename": filename,
            "slug": slug,
            "title": title,
            "date": date,
            "url": f"/{date.replace('-', '/')}/{slug}/",
        }

    def publish_draft(self, draft_filename: str, date: str | None = None) -> dict:
        """Move a draft from _drafts to _posts with today's date.

        Args:
            draft_filename: Filename of the draft (e.g. 'my-cool-post.md').
            date: Publish date as YYYY-MM-DD. Defaults to today.

        Returns:
            Dict with old and new file paths.
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        draft_path = self.blog_path / "_drafts" / draft_filename
        if not draft_path.exists():
            raise FileNotFoundError(f"Draft not found: {draft_filename}")

        # Read the draft and inject/update the date in front matter
        content = draft_path.read_text(encoding="utf-8")
        if "date:" not in content.split("---")[1] if "---" in content else "":
            content = content.replace("---\n", f"---\ndate: {date}\n", 1)

        new_filename = f"{date}-{draft_filename}"
        post_path = self.blog_path / "_posts" / new_filename
        post_path.write_text(content, encoding="utf-8")
        draft_path.unlink()

        slug = draft_filename.replace(".md", "")
        return {
            "action": "published",
            "from": str(draft_path),
            "to": str(post_path),
            "filename": new_filename,
            "url": f"/{date.replace('-', '/')}/{slug}/",
        }

    def list_drafts(self) -> list[dict]:
        """List all drafts in the _drafts folder."""
        drafts_dir = self.blog_path / "_drafts"
        if not drafts_dir.exists():
            return []

        drafts = []
        for f in sorted(drafts_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8", errors="ignore")
            title = self._extract_front_matter_field(content, "title") or f.stem
            drafts.append({
                "filename": f.name,
                "title": title,
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
        return drafts

    def list_recent_posts(self, count: int = 10) -> list[dict]:
        """List the most recent published posts."""
        posts_dir = self.blog_path / "_posts"
        if not posts_dir.exists():
            return []

        posts = []
        for f in sorted(posts_dir.glob("*.md"), reverse=True)[:count]:
            content = f.read_text(encoding="utf-8", errors="ignore")
            title = self._extract_front_matter_field(content, "title") or f.stem
            posts.append({
                "filename": f.name,
                "title": title,
                "date": f.name[:10],
            })
        return posts

    def get_common_tags(self) -> list[str]:
        """Return commonly used tags for reference."""
        return COMMON_TAGS

    def get_common_categories(self) -> list[str]:
        """Return commonly used categories for reference."""
        return COMMON_CATEGORIES

    # ── Internal helpers ─────────────────────────────────────────────

    def _build_front_matter(
        self,
        title: str,
        date: str | None = None,
        tags: list[str] | None = None,
        categories: list[str] | None = None,
        excerpt: str = "",
        series: str = "",
        part: int | None = None,
    ) -> str:
        """Build Jekyll YAML front matter."""
        lines = ["---"]
        lines.append(f'title: "{title}"')
        if date:
            lines.append(f"date: {date}")
        lines.append("layout: post")
        lines.append(f"author: {os.getenv('BLOG_AUTHOR', 'Your Name')}")

        if excerpt:
            lines.append(f'excerpt: "{excerpt}"')

        if tags:
            tag_str = ", ".join(tags)
            lines.append(f"tags: [{tag_str}]")

        if categories:
            cat_str = ", ".join(categories)
            lines.append(f"categories: [{cat_str}]")

        if series:
            lines.append(f'series: "{series}"')
            if part is not None:
                lines.append(f"series_part: {part}")

        lines.append("---")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _extract_front_matter_field(content: str, field: str) -> str | None:
        """Pull a single field value from Jekyll front matter."""
        match = re.search(rf'^{field}:\s*"?([^"\n]+)"?\s*$', content, re.MULTILINE)
        return match.group(1).strip() if match else None


class JekyllExpert:
    """Read, analyze, and fix Jekyll site content and configuration."""

    def __init__(self, blog_path: str = DEFAULT_BLOG_PATH):
        self.blog_path = Path(blog_path)

    # ── Read & Inspect ───────────────────────────────────────────────

    def read_post(self, filename: str) -> dict:
        """Read a post or draft and return its front matter and body separately.

        Args:
            filename: Post filename (e.g. '2023-12-13-minecraft-bot-part-1.md').
                      Searches _posts first, then _drafts.
        """
        filepath = self._find_file(filename)
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        front_matter, body = self._split_front_matter(content)

        return {
            "filename": filepath.name,
            "location": str(filepath.parent.name),
            "path": str(filepath),
            "front_matter_raw": front_matter,
            "front_matter_parsed": self._parse_front_matter(front_matter),
            "body": body,
            "word_count": len(body.split()),
            "line_count": len(body.splitlines()),
        }

    def read_file(self, relative_path: str) -> str:
        """Read any file in the Jekyll site by relative path.

        Args:
            relative_path: Path relative to the blog root (e.g. '_config.yml',
                          '_layouts/post.html', 'assets/css/style.css').
        """
        filepath = self.blog_path / relative_path
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")
        if not str(filepath.resolve()).startswith(str(self.blog_path.resolve())):
            raise ValueError(f"Path escapes blog directory: {relative_path}")
        return filepath.read_text(encoding="utf-8", errors="ignore")

    def read_config(self) -> str:
        """Read the Jekyll _config.yml file."""
        config_path = self.blog_path / "_config.yml"
        if not config_path.exists():
            raise FileNotFoundError("_config.yml not found in blog root")
        return config_path.read_text(encoding="utf-8", errors="ignore")

    def list_layouts(self) -> list[str]:
        """List available Jekyll layouts."""
        layouts_dir = self.blog_path / "_layouts"
        if not layouts_dir.exists():
            return []
        return sorted([f.name for f in layouts_dir.glob("*.html")])

    def list_includes(self) -> list[str]:
        """List available Jekyll includes/partials."""
        includes_dir = self.blog_path / "_includes"
        if not includes_dir.exists():
            return []
        return sorted([f.name for f in includes_dir.glob("*")])

    def site_structure(self) -> dict:
        """Get an overview of the Jekyll site structure."""
        structure = {
            "root": str(self.blog_path),
            "config_exists": (self.blog_path / "_config.yml").exists(),
            "directories": {},
            "top_level_files": [],
        }

        for item in sorted(self.blog_path.iterdir()):
            if item.name.startswith(".") and item.name != ".gitignore":
                continue
            if item.is_dir():
                file_count = sum(1 for _ in item.rglob("*") if _.is_file())
                structure["directories"][item.name] = file_count
            elif item.is_file():
                structure["top_level_files"].append(item.name)

        return structure

    # ── Analyze & Diagnose ───────────────────────────────────────────

    def analyze_post(self, filename: str) -> dict:
        """Analyze a post for common Jekyll issues.

        Checks: missing front matter fields, broken image links,
        heading hierarchy, orphaned liquid tags, etc.
        """
        post = self.read_post(filename)
        fm = post["front_matter_parsed"]
        body = post["body"]
        issues = []
        suggestions = []

        # Front matter checks
        if not fm.get("title"):
            issues.append("Missing 'title' in front matter")
        if not fm.get("layout"):
            suggestions.append("Consider adding 'layout: post' to front matter")
        if not fm.get("date") and "_posts" in str(post.get("path", "")):
            suggestions.append("Published post has no 'date' in front matter — Jekyll uses the filename date but explicit is safer")
        if not fm.get("tags") and not fm.get("tag"):
            suggestions.append("No tags defined — consider adding tags for discoverability")
        if not fm.get("excerpt") and not fm.get("description"):
            suggestions.append("No excerpt/description — useful for SEO and social previews")

        # Body checks
        headings = re.findall(r"^(#{1,6})\s+(.+)$", body, re.MULTILINE)
        if headings:
            levels = [len(h[0]) for h in headings]
            if levels and levels[0] != 2:
                issues.append(f"First heading is h{levels[0]} — should be h2 (h1 is typically the post title)")
            for i in range(1, len(levels)):
                if levels[i] > levels[i - 1] + 1:
                    issues.append(f"Heading level jumps from h{levels[i-1]} to h{levels[i]} ('{headings[i][1]}')")

        # Check for broken image references
        images = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", body)
        for alt, src in images:
            if not alt:
                suggestions.append(f"Image missing alt text: {src[:60]}")
            if src.startswith("/") or src.startswith("{{"):
                # Relative or liquid — check if file exists for relative paths
                if src.startswith("/"):
                    img_path = self.blog_path / src.lstrip("/")
                    if not img_path.exists():
                        issues.append(f"Image file not found: {src}")

        # Check for unclosed liquid tags
        liquid_opens = len(re.findall(r"\{%", body))
        liquid_closes = len(re.findall(r"%\}", body))
        if liquid_opens != liquid_closes:
            issues.append(f"Mismatched Liquid tags: {liquid_opens} opens vs {liquid_closes} closes")

        # Check for bare URLs that should be links
        bare_urls = re.findall(r"(?<!\()(https?://[^\s\)]+)(?!\))", body)
        if bare_urls:
            suggestions.append(f"Found {len(bare_urls)} bare URL(s) that could be markdown links")

        return {
            "filename": filename,
            "word_count": post["word_count"],
            "heading_count": len(headings),
            "image_count": len(images),
            "issues": issues,
            "suggestions": suggestions,
            "front_matter": fm,
        }

    # ── Edit & Fix ───────────────────────────────────────────────────

    def update_front_matter(self, filename: str, updates: dict) -> dict:
        """Update specific front matter fields in a post.

        Args:
            filename: Post or draft filename.
            updates: Dict of field → value to set (e.g. {'tags': '[python, ai]', 'excerpt': 'A cool post'}).
        """
        filepath = self._find_file(filename)
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        front_matter, body = self._split_front_matter(content)

        for key, value in updates.items():
            # Check if field already exists
            pattern = rf'^{re.escape(key)}:.*$'
            if re.search(pattern, front_matter, re.MULTILINE):
                front_matter = re.sub(pattern, f"{key}: {value}", front_matter, flags=re.MULTILINE)
            else:
                front_matter = front_matter.rstrip() + f"\n{key}: {value}"

        new_content = f"---\n{front_matter}\n---\n{body}"
        filepath.write_text(new_content, encoding="utf-8")

        return {
            "action": "front_matter_updated",
            "filename": filename,
            "updated_fields": list(updates.keys()),
            "path": str(filepath),
        }

    def replace_in_post(self, filename: str, old_text: str, new_text: str) -> dict:
        """Find and replace text in a post's body (not front matter).

        Args:
            filename: Post or draft filename.
            old_text: Exact text to find.
            new_text: Replacement text.
        """
        filepath = self._find_file(filename)
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        front_matter_raw, body = self._split_front_matter(content)

        count = body.count(old_text)
        if count == 0:
            return {"action": "no_match", "filename": filename, "search_text": old_text[:100]}

        new_body = body.replace(old_text, new_text)
        new_content = f"---\n{front_matter_raw}\n---\n{new_body}"
        filepath.write_text(new_content, encoding="utf-8")

        return {
            "action": "replaced",
            "filename": filename,
            "replacements": count,
            "path": str(filepath),
        }

    def write_file(self, relative_path: str, content: str) -> dict:
        """Write content to any file in the Jekyll site.

        Args:
            relative_path: Path relative to blog root.
            content: Full file content to write.
        """
        filepath = self.blog_path / relative_path
        if not str(filepath.resolve()).startswith(str(self.blog_path.resolve())):
            raise ValueError(f"Path escapes blog directory: {relative_path}")
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding="utf-8")
        return {
            "action": "written",
            "path": str(filepath),
            "size_bytes": filepath.stat().st_size,
        }

    # ── Helpers ───────────────────────────────────────────────────────

    def _find_file(self, filename: str) -> Path:
        """Find a post or draft by filename."""
        for folder in ["_posts", "_drafts"]:
            filepath = self.blog_path / folder / filename
            if filepath.exists():
                return filepath

        # Try partial match (without date prefix)
        for folder in ["_posts", "_drafts"]:
            folder_path = self.blog_path / folder
            if folder_path.exists():
                for f in folder_path.glob("*.md"):
                    if filename in f.name:
                        return f

        raise FileNotFoundError(
            f"Post not found: {filename}. Check blog_list_drafts or blog_list_recent_posts for available files."
        )

    @staticmethod
    def _split_front_matter(content: str) -> tuple[str, str]:
        """Split Jekyll file into front matter string and body string."""
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[1].strip(), parts[2]
        return "", content

    @staticmethod
    def _parse_front_matter(raw: str) -> dict:
        """Simple YAML-ish front matter parser (no PyYAML dependency)."""
        result = {}
        for line in raw.splitlines():
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                result[key] = value
        return result


# ════════════════════════════════════════════════════════════════════
#  BLOG WRITER — post scaffolding helpers
# ════════════════════════════════════════════════════════════════════

class BlogWriter:
    """Scaffolding tools for structuring and drafting blog posts.

    Posts follow a consistent anatomy:
      Foreword (personal story, honest reflection, no "in this post I will...")
      → Introduction (what you're building, reader takeaway)
      → Part 1…N (named phases, code walkthroughs with Key-lessons callouts)
      → What I'd Do Differently
      → Conclusion
      → Resources

    Titles consistently use "ProjectName: Short Descriptive Subtitle" format.
    """

    # ── Title patterns seen in the wild ─────────────────────────────
    _TITLE_SUBTITLES = [
        "{project}: Building {description}",
        "{project}: How I {action}",
        "{project}: Getting {goal} with {tech}",
        "{project}: A {adjective} Approach to {description}",
        "{project}: When {setup} Goes {outcome}",
    ]

    _FOREWORD_STARTERS = [
        "started with a conversation",
        "wasn't supposed to be this complicated",
        "I'll be honest — I had no idea what I was doing",
        "This one started as a side-thought",
        "I keep telling myself I'll do things properly next time",
    ]

    def __init__(self, blog_path: str = DEFAULT_BLOG_PATH):
        self.blog_path = Path(blog_path)
        self._blog = BlogTools(blog_path)

    # ── Public tools ─────────────────────────────────────────────────

    def suggest_titles(self, topic: str, description: str = "") -> list[str]:
        """Return 5 title suggestions in 'ProjectName: Subtitle' format.

        Args:
            topic: The project or topic name (e.g. "RaceFlow", "a Discord bot").
            description: Optional one-line description of what it does or the angle.
        """
        project = topic.strip()
        desc = description.strip() or "something that definitely works"

        # Derive some fill values from the description
        words = desc.lower().split()
        tech_words = [w for w in words if w in (
            "python", "n8n", "fastapi", "discord", "docker", "click",
            "openai", "llm", "ai", "rust", "typescript", "react",
            "jekyll", "github", "automation", "api"
        )]
        tech = tech_words[0].capitalize() if tech_words else "Code"
        action_words = [w for w in words if w in (
            "built", "automated", "fixed", "tracked", "generated",
            "connected", "deployed", "scraped", "parsed"
        )]
        action = action_words[0] if action_words else f"Built {desc[:30]}"

        suggestions = [
            f"{project}: {desc[:50]}",
            f"{project}: A Story of {tech} and Questionable Decisions",
            f"{project}: How I {action.capitalize()} Without Breaking Everything",
            f"{project}: Building {desc[:40]} (And What I'd Do Differently)",
            f"{project}: The Part Where It Actually Worked",
        ]
        return suggestions

    def scaffold_post(
        self,
        title: str,
        topic_summary: str,
        post_type: str = "project",
        tags: list | None = None,
        series: str = "",
        part: int | None = None,
    ) -> dict:
        """Create a fully scaffolded _draft with artoffailing.com's section structure.

        Saves to _drafts/ and returns the filename and path.  Each section is
        pre-filled with [FILL: …] placeholders so you know exactly what belongs
        where without staring at a blank page.

        Args:
            title: Full post title (e.g. "TracksMartin: Hits on Demand").
            topic_summary: 1-3 sentence description of what the post covers.
            post_type: "project" (default), "tutorial", "series_part", or "thoughts".
            tags: List of tags. Defaults to a sensible starter set.
            series: Series name if this is part of a series (e.g. "RaceFlow").
            part: Part number if this is a series post (e.g. 1).
        """
        if tags is None:
            tags = ["python", "projects"]

        # Build the body based on post type
        if post_type == "series_part" or (series and part):
            body = self._series_body(title, topic_summary, series or title, part or 1)
        elif post_type == "tutorial":
            body = self._tutorial_body(title, topic_summary)
        elif post_type == "thoughts":
            body = self._thoughts_body(title, topic_summary)
        else:
            body = self._project_body(title, topic_summary)

        result = self._blog.create_draft(
            title=title,
            tags=tags,
            category="projects" if post_type in ("project", "series_part") else post_type,
            content=body,
        )
        return result

    def draft_foreword(
        self,
        project_name: str,
        context: str,
        tone_notes: str = "",
    ) -> str:
        """Return a foreword template for the given project.

        The foreword is always the hardest paragraph — this gets you unstuck.
        It returns a fill-in-the-blanks skeleton:
        personal hook → honest admission → external trigger → transition to tech.

        Args:
            project_name: Name of the project or thing the post is about.
            context: 2-4 sentences explaining what it is and why you built it.
            tone_notes: Optional style notes (e.g. "frustrated with existing tools",
                        "friend suggested it", "obvious in retrospect").
        """
        tone_hint = f"\n\nTone notes you provided: {tone_notes}" if tone_notes else ""
        return f"""## Foreword

<!-- FILL IN: Replace this entire block with your foreword. Keep it personal.
     Context you provided: {context}{tone_hint}

     Foreword formula:
       1. Open with HOW you ended up here — not "in this post I will..."
          e.g. "It started with a conversation about..." / "I'd been meaning to fix this for months..."
       2. Admit something honest — uncertainty, over-complication, or a false start.
          e.g. "I had no idea what I was doing." / "This was obviously going to be messier than I thought."
       3. Name the external trigger if there was one (a friend, a bug, a tweet, a piece of data).
       4. One sentence that transitions naturally toward the technical content.
          Do NOT write "in this post I will show you" or "this tutorial will cover".
-->

I'd been putting off building {project_name} for longer than I'd like to admit.
[FILL: What finally pushed you to actually start? A conversation? A problem that got annoying enough?]

[FILL: What was your honest first reaction when you looked at the scope? Overwhelmed?
Excited? "How hard could it be?" End on a line that naturally leads into the Introduction.]
"""

    # ── Body builders ─────────────────────────────────────────────────

    def _project_body(self, title: str, summary: str) -> str:
        return f"""## Foreword

[FILL: Personal story — what led you to this? The moment it clicked (or didn't).
Be honest. Reference a friend, a frustration, or a "this is obviously a bad idea" moment.
No "in this post I will..." openings.]


## Introduction

{summary}

[FILL: Technical context — what you built, stack, repo link if applicable.
Tell the reader what they'll walk away knowing.]


## Part 1: [Name the first phase]

### [First subsection]

[FILL: Walk through the approach. Show code. Explain the *why*, not just the *what*.]

```python
# [FILL: key code snippet]
```

**Key lessons:**
- [FILL]
- [FILL]


## Part 2: [Name the second phase]

### [Subsection]

[FILL]

```python
# [FILL]
```

**Key lessons:**
- [FILL]


## Part 3: [Add or remove parts as needed]

[FILL]


## What I'd Do Differently

- [FILL: Testing — what would you add?]
- [FILL: Configuration / hardcoded values you'd extract]
- [FILL: Architecture decision you'd revisit]
- [FILL: Anything that bit you that's worth warning others about]


## Conclusion

[FILL: What you built, what you learned. Keep it short — 2-4 sentences.
Link to the GitHub repo. No "I hope you found this useful" or similar.]


## Resources

- [FILL: link] — description
- [FILL: link] — description
"""

    def _tutorial_body(self, title: str, summary: str) -> str:
        return f"""## Foreword

[FILL: Why this tutorial exists. What problem you kept seeing or hitting yourself.
No "in this tutorial I will..." openings.]


## Introduction

{summary}

**What you'll need:**
- [FILL: prerequisite 1]
- [FILL: prerequisite 2]

**What you'll build:** [FILL: one clear sentence]


## Step 1: [First step name]

[FILL: explain what this step achieves before showing code]

```bash
# [FILL: setup/install commands]
```

[FILL: explain what just happened and why]


## Step 2: [Second step name]

[FILL]

```python
# [FILL]
```

**Key lessons:**
- [FILL]


## Step 3: [Add or remove steps as needed]

[FILL]


## Wrapping Up

[FILL: summary of what was built, next steps, link to repo or related posts]


## Resources

- [FILL: link] — description
"""

    def _series_body(self, title: str, summary: str, series: str, part: int) -> str:
        prev_part = part - 1
        prev_arrow = "← [Previous part]" if part > 1 else ""
        prev_ref = str(prev_part) if part > 1 else "N-1"
        return f"""{{% if page.series %}}
<div class="series-nav">
  Part {part} of the {series} series.
  {prev_arrow}
</div>
{{% endif %}}

## Foreword

[FILL: What happened since the last part? What broke, what changed, what you figured out?
Brief recap of where Part {prev_ref} left off — 2 sentences max.]


## Introduction

{summary}

[FILL: What this part specifically covers. What the reader needs from previous parts.]


## Where We Left Off

[FILL: Quick "previously on..." summary — 3-5 bullets max. Link to Part {part - 1 if part > 1 else 1}.]


## Part {part} Begins: [Name the focus of this part]

### [Subsection]

[FILL: Walk through the changes/additions. Show code. Explain the why.]

```python
# [FILL]
```

**Key lessons:**
- [FILL]


## [Next section]

[FILL]


## What's Next

[FILL: What Part {part + 1} will cover. What you haven't solved yet. Honest about the state of things.]


## Resources

- [FILL: link] — description
"""

    def _thoughts_body(self, title: str, summary: str) -> str:
        return f"""## Foreword

[FILL: What triggered this post? A conversation, a frustration, something you read?
Be honest about where the idea came from.]


## [First section — name the argument or observation]

{summary}

[FILL: Develop the first idea. Personal experience + broader observation.]


## [Second section]

[FILL: Where does this go? Push back on your own point if you have a counterargument.]


## [Third section — optional]

[FILL]


## Where This Leaves Me

[FILL: What do you actually think? What are you going to do differently?
No need to wrap it up neatly — it's okay to end with an open question.]
"""

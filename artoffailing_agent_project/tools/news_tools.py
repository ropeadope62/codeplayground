"""
News tools — fetch and compile news from RSS feeds into markdown reports.

No API key required. Uses public RSS feeds from major outlets.
Categories are customizable and can be combined.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import sys
import logging
from datetime import datetime, timezone
from typing import Optional
from xml.etree import ElementTree

logger = logging.getLogger("workstation-agent.news")

# ── Feed registry ────────────────────────────────────────────────────
# Each category maps to a list of (source_name, rss_url) tuples.
# Add or remove feeds to taste.

FEEDS: dict[str, list[tuple[str, str]]] = {
    "tech": [
        ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
        ("Hacker News", "https://hnrss.org/frontpage"),
        ("TechCrunch", "https://techcrunch.com/feed/"),
        ("Wired", "https://www.wired.com/feed/rss"),
    ],
    "cybersecurity": [
        ("Krebs on Security", "https://krebsonsecurity.com/feed/"),
        ("The Hacker News", "https://feeds.feedburner.com/TheHackersNews"),
        ("Dark Reading", "https://www.darkreading.com/rss.xml"),
        ("BleepingComputer", "https://www.bleepingcomputer.com/feed/"),
        ("Threatpost", "https://threatpost.com/feed/"),
    ],
    "ai": [
        ("MIT Tech Review AI", "https://www.technologyreview.com/topic/artificial-intelligence/feed"),
        ("OpenAI Blog", "https://openai.com/blog/rss.xml"),
        ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
        ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
        ("Hacker News", "https://hnrss.org/frontpage?q=AI+OR+LLM+OR+GPT"),
    ],
    "world": [
        ("Reuters World", "https://feeds.reuters.com/Reuters/worldNews"),
        ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("AP News", "https://rsshub.app/apnews/topics/apf-topnews"),
        ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ],
    "business": [
        ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
        ("Bloomberg", "https://feeds.bloomberg.com/markets/news.rss"),
        ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147"),
        ("Financial Times", "https://www.ft.com/rss/home"),
    ],
    "science": [
        ("Nature", "https://www.nature.com/nature.rss"),
        ("New Scientist", "https://www.newscientist.com/section/news/feed/"),
        ("Phys.org", "https://phys.org/rss-feed/"),
        ("Science Daily", "https://www.sciencedaily.com/rss/all.xml"),
    ],
    "canada": [
        ("CBC News", "https://rss.cbc.ca/lineup/topstories.xml"),
        ("CBC Montreal", "https://rss.cbc.ca/lineup/canada-montreal.xml"),
        ("Global News", "https://globalnews.ca/feed/"),
        ("CTV News", "https://www.ctvnews.ca/rss/ctvnews-ca-top-stories-public-rss-1.822009"),
    ],
    "gaming": [
        ("Kotaku", "https://kotaku.com/rss"),
        ("IGN", "https://feeds.feedburner.com/ign/all"),
        ("PC Gamer", "https://www.pcgamer.com/rss/"),
        ("Eurogamer", "https://www.eurogamer.net/feed"),
    ],
}


def _fetch_feed(url: str, timeout: int = 10) -> list[dict]:
    """Fetch and parse a single RSS/Atom feed. Returns list of article dicts."""
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "WorkstationAgent/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
    except (urllib.error.URLError, OSError) as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return []

    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError:
        return []

    articles = []

    # RSS 2.0 format
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()

        if title:
            # Strip HTML tags from description
            import re
            desc_clean = re.sub(r"<[^>]+>", "", desc)[:300]

            articles.append({
                "title": title,
                "link": link,
                "description": desc_clean,
                "published": pub_date,
            })

    # Atom format (if no RSS items found)
    if not articles:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall(".//atom:entry", ns) or root.findall(".//entry"):
            title = ""
            link = ""
            desc = ""
            pub_date = ""

            title_el = entry.find("atom:title", ns) or entry.find("title")
            if title_el is not None and title_el.text:
                title = title_el.text.strip()

            link_el = entry.find("atom:link", ns) or entry.find("link")
            if link_el is not None:
                link = link_el.get("href", "").strip()

            summary_el = entry.find("atom:summary", ns) or entry.find("summary") or entry.find("atom:content", ns) or entry.find("content")
            if summary_el is not None and summary_el.text:
                import re
                desc = re.sub(r"<[^>]+>", "", summary_el.text.strip())[:300]

            updated_el = entry.find("atom:updated", ns) or entry.find("updated") or entry.find("atom:published", ns) or entry.find("published")
            if updated_el is not None and updated_el.text:
                pub_date = updated_el.text.strip()

            if title:
                articles.append({
                    "title": title,
                    "link": link,
                    "description": desc,
                    "published": pub_date,
                })

    return articles


class NewsTools:
    """Fetch news from RSS feeds and compile markdown reports."""

    def get_available_categories(self) -> list[str]:
        """Return all available news categories."""
        return list(FEEDS.keys())

    def fetch_news(
        self,
        categories: list[str],
        max_per_source: int = 5,
    ) -> dict[str, list[dict]]:
        """Fetch news articles for the given categories.

        Args:
            categories: List of category names (e.g. ['tech', 'cybersecurity']).
            max_per_source: Max articles per source feed.

        Returns:
            Dict mapping category → list of article dicts.
        """
        results = {}

        for category in categories:
            cat_lower = category.lower().strip()
            if cat_lower not in FEEDS:
                results[category] = [{"error": f"Unknown category '{category}'. Available: {', '.join(FEEDS.keys())}"}]
                continue

            cat_articles = []
            for source_name, feed_url in FEEDS[cat_lower]:
                articles = _fetch_feed(feed_url)
                for article in articles[:max_per_source]:
                    article["source"] = source_name
                cat_articles.extend(articles[:max_per_source])

            results[cat_lower] = cat_articles

        return results

    def compile_report(
        self,
        categories: list[str],
        max_per_source: int = 5,
    ) -> str:
        """Fetch news and compile a markdown report.

        Args:
            categories: List of category names.
            max_per_source: Max articles per source.

        Returns:
            Formatted markdown string with the news report.
        """
        news = self.fetch_news(categories, max_per_source)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        lines = [
            f"# News Briefing",
            f"*Generated: {now}*\n",
        ]

        for category, articles in news.items():
            lines.append(f"## {category.title()}\n")

            if not articles:
                lines.append("*No articles found for this category.*\n")
                continue

            if articles and "error" in articles[0]:
                lines.append(f"*{articles[0]['error']}*\n")
                continue

            # Group by source
            by_source: dict[str, list[dict]] = {}
            for article in articles:
                source = article.get("source", "Unknown")
                by_source.setdefault(source, []).append(article)

            for source, source_articles in by_source.items():
                lines.append(f"### {source}\n")
                for article in source_articles:
                    title = article["title"]
                    link = article.get("link", "")
                    desc = article.get("description", "")

                    if link:
                        lines.append(f"- [{title}]({link})")
                    else:
                        lines.append(f"- {title}")

                    if desc:
                        # Trim to first sentence or 150 chars
                        short = desc[:150].rsplit(" ", 1)[0]
                        if len(desc) > 150:
                            short += "..."
                        lines.append(f"  {short}\n")
                    else:
                        lines.append("")

            lines.append("---\n")

        return "\n".join(lines)

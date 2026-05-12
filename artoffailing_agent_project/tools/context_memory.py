"""
context_memory.py — Semantic activity memory powered by ChromaDB.

Indexes daily notes, journal entries, and digests into a local ChromaDB
collection for semantic retrieval. This gives the agent long-term memory
across sessions — ask "what was I working on with Varonis last week?" and
get real answers instead of brute-force scanning flat files.

Storage: data/chroma/ (embedded, no server, no network).
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import json
import re
import logging
from pathlib import Path
from datetime import datetime, date, timedelta
from mcp.server import FastMCP

import chromadb
from chromadb.config import Settings

logger = logging.getLogger("workstation-agent.context_memory")

_BASE = Path(__file__).resolve().parent.parent
CHROMA_DIR = _BASE / "data" / "chroma"
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# Paths to data sources
DAILY_NOTES_DIR = _BASE / "notes" / "daily"
NOTES_FILE = _BASE / "notes" / "notes.json"
DIGEST_DIR = _BASE / "notes" / "digests"
JOURNAL_DIR = Path("~/Documents/work/journal").expanduser()

COLLECTION_NAME = "activity_context"


class ContextMemory:
    """Embedded ChromaDB-backed semantic memory for daily activity."""

    def __init__(self):
        self._client = None
        self._collection = None

    @property
    def client(self) -> chromadb.ClientAPI:
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=str(CHROMA_DIR),
                settings=Settings(anonymized_telemetry=False),
            )
        return self._client

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def index_entry(
        self,
        text: str,
        entry_date: str,
        source: str,
        category: str = "",
        tags: list[str] | None = None,
    ) -> str:
        """Index a single activity entry into ChromaDB.

        Args:
            text: The content to index.
            entry_date: YYYY-MM-DD date of the entry.
            source: Origin — 'daily_note', 'journal', 'digest', 'note', 'meeting'.
            category: 'work', 'personal', or empty.
            tags: Optional tag list.

        Returns:
            The document ID.
        """
        doc_id = f"{source}:{entry_date}:{hash(text) & 0xFFFFFFFF:08x}"
        date_int = int(entry_date.replace("-", ""))  # 2026-04-14 -> 20260414
        metadata = {
            "date": entry_date,
            "date_int": date_int,
            "source": source,
            "category": category or "general",
            "tags": ",".join(tags) if tags else "",
        }
        self.collection.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata],
        )
        return doc_id

    def index_day(self, target_date: str = "") -> dict:
        """Index all activity from a given date into ChromaDB.

        Pulls from daily notes, journal entries, persistent notes, and digests.
        Safe to call multiple times — uses upsert, so duplicates are overwritten.

        Args:
            target_date: YYYY-MM-DD. Defaults to today.

        Returns:
            Summary of what was indexed.
        """
        d = target_date or date.today().isoformat()
        indexed = {"date": d, "entries": 0, "sources": []}

        # ── Daily notes ──────────────────────────────────────
        daily_file = DAILY_NOTES_DIR / f"{d}.json"
        if daily_file.exists():
            try:
                entries = json.loads(daily_file.read_text(encoding="utf-8"))
                for e in entries:
                    self.index_entry(
                        text=e["text"],
                        entry_date=d,
                        source="daily_note",
                        category=e.get("category", ""),
                        tags=e.get("tags", []),
                    )
                    indexed["entries"] += 1
                if entries:
                    indexed["sources"].append("daily_notes")
            except (json.JSONDecodeError, KeyError):
                pass

        # ── Journal entries ──────────────────────────────────
        journal_file = JOURNAL_DIR / f"{d}.md"
        if journal_file.exists():
            content = journal_file.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("- **") and "** —" in line:
                    match = re.match(r"- \*\*\d{2}:\d{2}\*\* — (.+)", line)
                    if match:
                        entry_text = match.group(1)
                        tags = re.findall(r"`#([^`]+)`", entry_text)
                        clean = re.sub(r"\s*`#[^`]+`", "", entry_text).strip()
                        self.index_entry(
                            text=clean,
                            entry_date=d,
                            source="journal",
                            category="work",
                            tags=tags,
                        )
                        indexed["entries"] += 1
            if indexed["entries"] > 0 and "journal" not in indexed["sources"]:
                indexed["sources"].append("journal")

        # ── Persistent notes from this date ──────────────────
        if NOTES_FILE.exists():
            try:
                all_notes = json.loads(NOTES_FILE.read_text(encoding="utf-8"))
                day_notes = [
                    n for n in all_notes
                    if n.get("date", n.get("created", ""))[:10] == d
                ]
                for n in day_notes:
                    self.index_entry(
                        text=n["text"],
                        entry_date=d,
                        source="note",
                        tags=[n["tag"]] if n.get("tag") else [],
                    )
                    indexed["entries"] += 1
                if day_notes:
                    indexed["sources"].append("notes")
            except (json.JSONDecodeError, KeyError):
                pass

        # ── Digest (index as a single document for context) ──
        digest_file = DIGEST_DIR / f"{d}.txt"
        if digest_file.exists():
            digest_text = digest_file.read_text(encoding="utf-8")
            if digest_text.strip():
                self.index_entry(
                    text=digest_text,
                    entry_date=d,
                    source="digest",
                )
                indexed["entries"] += 1
                indexed["sources"].append("digest")

        return indexed

    def search(
        self,
        query: str,
        n_results: int = 10,
        source: str = "",
        category: str = "",
        date_from: str = "",
        date_to: str = "",
    ) -> list[dict]:
        """Semantic search across indexed activity.

        Args:
            query: Natural language query.
            n_results: Max results to return.
            source: Filter by source type (daily_note, journal, digest, note).
            category: Filter by category (work, personal).
            date_from: Filter entries on or after this date (YYYY-MM-DD).
            date_to: Filter entries on or before this date (YYYY-MM-DD).

        Returns:
            List of matching entries with text, metadata, and distance score.
        """
        where_filters = []
        if source:
            where_filters.append({"source": source})
        if category:
            where_filters.append({"category": category})
        if date_from:
            where_filters.append({"date_int": {"$gte": int(date_from.replace("-", ""))}})
        if date_to:
            where_filters.append({"date_int": {"$lte": int(date_to.replace("-", ""))}})

        where = None
        if len(where_filters) == 1:
            where = where_filters[0]
        elif len(where_filters) > 1:
            where = {"$and": where_filters}

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where if where else None,
            )
        except Exception as e:
            logger.warning("ChromaDB query failed: %s", e)
            return []

        entries = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else None
                entries.append({
                    "text": doc[:500],
                    "date": meta.get("date", ""),
                    "source": meta.get("source", ""),
                    "category": meta.get("category", ""),
                    "tags": meta.get("tags", ""),
                    "relevance": round(1 - distance, 3) if distance is not None else None,
                })

        return entries

    def get_relevant_context(self, query: str, days_back: int = 7, n_results: int = 5) -> str:
        """Return a formatted context string for use in briefings/reviews.

        Searches recent activity and returns a concise summary of relevant entries.
        """
        date_from = (date.today() - timedelta(days=days_back)).isoformat()
        results = self.search(
            query=query,
            n_results=n_results,
            date_from=date_from,
        )
        if not results:
            return ""

        lines = []
        for r in results:
            source_label = r["source"].replace("_", " ").title()
            tags = f" [{r['tags']}]" if r["tags"] else ""
            lines.append(f"- [{r['date']}] ({source_label}{tags}) {r['text'][:200]}")
        return "\n".join(lines)

    def reindex_range(self, days_back: int = 30) -> dict:
        """Reindex activity for the last N days. Useful for initial setup."""
        today = date.today()
        total = {"days_processed": 0, "total_entries": 0}
        for i in range(days_back):
            d = (today - timedelta(days=i)).isoformat()
            result = self.index_day(d)
            if result["entries"] > 0:
                total["days_processed"] += 1
                total["total_entries"] += result["entries"]
        return total

    def stats(self) -> dict:
        """Return stats about the ChromaDB collection."""
        count = self.collection.count()
        return {
            "collection": COLLECTION_NAME,
            "total_documents": count,
            "storage_path": str(CHROMA_DIR),
        }


def register_context_memory(mcp: FastMCP, memory: ContextMemory):
    """Register context memory tools on the MCP server."""

    @mcp.tool()
    def search_activity_context(
        query: str,
        n_results: int = 10,
        source: str = "",
        category: str = "",
        date_from: str = "",
        date_to: str = "",
    ) -> str:
        """
        Semantic search across all indexed activity — notes, journal, digests.

        Ask natural language questions like:
          - "What was I working on with Varonis last week?"
          - "CyberArk meetings and follow-ups"
          - "What did I do on Monday?"

        Uses ChromaDB for vector similarity search with optional filters.

        Args:
            query:     Natural language search query.
            n_results: Max results (default 10).
            source:    Filter by source: daily_note, journal, digest, note.
            category:  Filter by category: work, personal.
            date_from: Only entries on or after this date (YYYY-MM-DD).
            date_to:   Only entries on or before this date (YYYY-MM-DD).
        """
        results = memory.search(query, n_results, source, category, date_from, date_to)
        if not results:
            return json.dumps({"results": [], "message": "No matching activity found."})
        return json.dumps({"results": results, "count": len(results)}, indent=2)

    @mcp.tool()
    def index_activity(target_date: str = "", days_back: int = 0) -> str:
        """
        Index daily activity into the semantic memory store.

        Pulls notes, journal entries, and digests into ChromaDB for
        later semantic search. Safe to run multiple times — uses upsert.

        Args:
            target_date: YYYY-MM-DD to index a specific day. Defaults to today.
            days_back:   If > 0, reindex the last N days instead of a single day.
        """
        if days_back > 0:
            result = memory.reindex_range(days_back)
            return json.dumps({
                "action": "reindexed",
                "days_back": days_back,
                **result,
            }, indent=2)
        else:
            result = memory.index_day(target_date)
            return json.dumps({"action": "indexed", **result}, indent=2)

    @mcp.tool()
    def context_memory_stats() -> str:
        """Show statistics about the semantic memory store (document count, storage path)."""
        return json.dumps(memory.stats(), indent=2)

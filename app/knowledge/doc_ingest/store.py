"""Corpus store — versioned JSON files in app/knowledge/corpus/.

Each ingested document becomes a JSON file named by its slug.
The store supports CRUD operations and provides a merged view
for injection into worker prompts via get_training_context().
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.knowledge.doc_ingest.ingester import CorpusEntry

logger = logging.getLogger(__name__)

# Corpus lives next to base_training.py
CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"


class CorpusStore:
    """Manages versioned corpus files on disk."""

    def __init__(self, corpus_dir: Path | None = None) -> None:
        self._dir = corpus_dir or CORPUS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, slug: str) -> Path:
        return self._dir / f"{slug}.json"

    def save(self, entry: CorpusEntry) -> Path:
        """Save a corpus entry to disk. Overwrites if slug exists, bumps version."""
        path = self._path_for(entry.slug)

        if path.exists():
            existing = self._load_file(path)
            entry.version = existing.get("version", 0) + 1

        data = {
            "slug": entry.slug,
            "title": entry.title,
            "source_summary": entry.source_summary,
            "source_hash": entry.source_hash,
            "version": entry.version,
            "principles": entry.principles,
            "frameworks": entry.frameworks,
            "examples": entry.examples,
            "anti_patterns": entry.anti_patterns,
            "vocabulary": entry.vocabulary,
        }

        path.write_text(json.dumps(data, indent=2))
        logger.info("corpus.saved slug=%s version=%d path=%s", entry.slug, entry.version, path)
        return path

    def get(self, slug: str) -> dict[str, Any] | None:
        """Load a single corpus entry by slug."""
        path = self._path_for(slug)
        if not path.exists():
            return None
        return self._load_file(path)

    def list_all(self) -> list[dict[str, Any]]:
        """List all corpus entries (metadata only, no full content)."""
        entries = []
        for path in sorted(self._dir.glob("*.json")):
            data = self._load_file(path)
            if data:
                entries.append({
                    "slug": data.get("slug", path.stem),
                    "title": data.get("title", ""),
                    "source_summary": data.get("source_summary", ""),
                    "version": data.get("version", 1),
                    "principles_count": len(data.get("principles", [])),
                    "frameworks_count": len(data.get("frameworks", [])),
                    "examples_count": len(data.get("examples", [])),
                })
        return entries

    def delete(self, slug: str) -> bool:
        """Delete a corpus entry. Returns True if it existed."""
        path = self._path_for(slug)
        if path.exists():
            path.unlink()
            logger.info("corpus.deleted slug=%s", slug)
            return True
        return False

    def load_all_for_context(self, max_chars: int = 50_000) -> str:
        """Load all corpus entries and format them for prompt injection.

        Merges all principles, frameworks, examples, and anti-patterns
        from all corpus files into a single text block, respecting
        a character budget to avoid blowing up the context window.
        """
        all_principles: list[str] = []
        all_frameworks: list[str] = []
        all_examples: list[str] = []
        all_anti_patterns: list[str] = []

        for path in sorted(self._dir.glob("*.json")):
            data = self._load_file(path)
            if not data:
                continue

            source = data.get("title", path.stem)

            for p in data.get("principles", []):
                all_principles.append(
                    f"- **{p.get('name', '')}** ({source}): {p.get('description', '')}"
                )

            for f in data.get("frameworks", []):
                steps = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(f.get("steps", [])))
                all_frameworks.append(
                    f"**{f.get('name', '')}** ({source}): {f.get('description', '')}\n"
                    f"  When to use: {f.get('when_to_use', '')}\n{steps}"
                )

            for e in data.get("examples", []):
                all_examples.append(
                    f"Context: {e.get('context', '')}\n"
                    f"  Good: {e.get('good_version', '')}\n"
                    f"  Bad: {e.get('bad_version', '')}\n"
                    f"  Why: {e.get('why_good_is_better', '')}"
                )

            for ap in data.get("anti_patterns", []):
                all_anti_patterns.append(
                    f"- **{ap.get('name', '')}**: {ap.get('description', '')} "
                    f"→ {ap.get('what_to_do_instead', '')}"
                )

        sections: list[str] = []
        if all_principles:
            sections.append(
                "## Ingested Principles\n\n" + "\n".join(all_principles)
            )
        if all_frameworks:
            sections.append(
                "## Ingested Frameworks\n\n" + "\n\n".join(all_frameworks)
            )
        if all_examples:
            sections.append(
                "## Ingested Examples\n\n" + "\n\n".join(all_examples)
            )
        if all_anti_patterns:
            sections.append(
                "## Ingested Anti-Patterns\n\n" + "\n".join(all_anti_patterns)
            )

        merged = "\n\n---\n\n".join(sections)

        # Respect token budget
        if len(merged) > max_chars:
            merged = merged[:max_chars] + "\n\n[… truncated to fit context budget]"

        return merged

    @staticmethod
    def _load_file(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("corpus.load_failed path=%s error=%s", path, exc)
            return {}


# Module-level singleton
corpus_store = CorpusStore()

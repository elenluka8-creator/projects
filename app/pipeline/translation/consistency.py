"""Job-scoped translation consistency memory.

Maintains terminology, named entities, and chapter context across batches
within a single job run (DEC-005 §Consistency Strategy).

Rules:
- Scoped to one job run — never reused across books or jobs.
- Mutable (updated after each batch) but not shared across concurrent workers.
- Serialized to a compact context string for prompt inclusion.
- Follows job retention window for cleanup.
- Persisted to DB (job_consistency_snapshots) so state survives worker restarts.

Eviction strategy: LFU (Least Frequently Used) with person-entity protection.
Entries with the highest hit count are retained. Entities of type "person" are
never evicted automatically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

# Maximum characters included in the prompt context string.
_MAX_CONTEXT_CHARS: int = 2000
# Limits raised to handle books up to ~200k words (≈160 batches).
_MAX_TERMS: int = 200
_MAX_ENTITIES: int = 150


@dataclass
class ConsistencyMemory:
    """Job-scoped consistency state with LFU eviction and DB persistence support.

    Fields (per ARCH §Consistency Strategy):
        terminology_map           -- source_term → target_translation
        named_entity_registry     -- entity_name → {translation, type}
        chapter_context_summary   -- Rolling one-sentence summary of recent content
        ambiguity_notes           -- Unresolved items for future improvement
        term_hits                 -- Hit count per terminology entry (LFU signal)
        entity_hits               -- Hit count per entity entry (LFU signal)
    """

    terminology_map: Dict[str, str] = field(default_factory=dict)
    named_entity_registry: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    chapter_context_summary: str = ""
    ambiguity_notes: List[str] = field(default_factory=list)
    # LFU counters — not exposed to prompts, used only for eviction decisions.
    term_hits: Dict[str, int] = field(default_factory=dict)
    entity_hits: Dict[str, int] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "ConsistencyMemory":
        return cls()

    def update(
        self,
        new_terms: Dict[str, str],
        new_entities: Dict[str, Dict[str, Any]],
        chapter_summary: str,
    ) -> None:
        """Update in-place after a batch completes.

        - Increments hit count for entries already in memory (re-seen = more frequent).
        - Sets hit count to 1 for brand-new entries.
        - Evicts LFU entries (protecting person entities) when limits are exceeded.
        """
        if new_terms:
            for src, tgt in new_terms.items():
                if src in self.terminology_map:
                    self.term_hits[src] = self.term_hits.get(src, 1) + 1
                else:
                    self.terminology_map[src] = tgt
                    self.term_hits[src] = 1

            if len(self.terminology_map) > _MAX_TERMS:
                self._evict_terms()

        if new_entities:
            for name, meta in new_entities.items():
                if name in self.named_entity_registry:
                    self.entity_hits[name] = self.entity_hits.get(name, 1) + 1
                    # Update translation/type if provided (allow corrections).
                    self.named_entity_registry[name].update(meta)
                else:
                    self.named_entity_registry[name] = meta
                    self.entity_hits[name] = 1

            if len(self.named_entity_registry) > _MAX_ENTITIES:
                self._evict_entities()

        if chapter_summary:
            self.chapter_context_summary = chapter_summary

    def _evict_terms(self) -> None:
        """Remove the least-frequently-used terms until at or below the limit."""
        excess = len(self.terminology_map) - _MAX_TERMS
        if excess <= 0:
            return
        # Sort ascending by hit count; evict the rarest entries first.
        by_hits = sorted(self.term_hits.items(), key=lambda kv: kv[1])
        for key, _ in by_hits[:excess]:
            self.terminology_map.pop(key, None)
            self.term_hits.pop(key, None)

    def _evict_entities(self) -> None:
        """Remove LFU entities; never evict person-type entities."""
        excess = len(self.named_entity_registry) - _MAX_ENTITIES
        if excess <= 0:
            return
        # Candidate pool: non-person entities, sorted by hit count ascending.
        candidates = [
            (name, self.entity_hits.get(name, 1))
            for name, meta in self.named_entity_registry.items()
            if meta.get("type", "") != "person"
        ]
        candidates.sort(key=lambda kv: kv[1])
        for name, _ in candidates[:excess]:
            self.named_entity_registry.pop(name, None)
            self.entity_hits.pop(name, None)

    def to_context_string(self) -> str:
        """Compact context string for prompt inclusion.

        Shows the most-referenced entries first so the prompt stays relevant.
        Truncated to _MAX_CONTEXT_CHARS to prevent prompt bloat.
        """
        parts: List[str] = []

        if self.terminology_map:
            top_terms = sorted(
                self.terminology_map.items(),
                key=lambda kv: self.term_hits.get(kv[0], 1),
                reverse=True,
            )[:30]
            items = [f'"{k}" → "{v}"' for k, v in top_terms]
            parts.append("Established terms: " + ", ".join(items))

        if self.named_entity_registry:
            top_entities = sorted(
                self.named_entity_registry.items(),
                key=lambda kv: self.entity_hits.get(kv[0], 1),
                reverse=True,
            )[:20]
            items = []
            for k, v in top_entities:
                meta = v.get("type", "?")
                gender = v.get("gender", "")
                if gender and gender != "none":
                    meta = f"{meta},{gender}"
                items.append(f'"{k}" → "{v.get("translation", k)}" ({meta})')
            parts.append("Known names/entities: " + ", ".join(items))

        if self.chapter_context_summary:
            parts.append(f"Recent context: {self.chapter_context_summary}")

        text = "\n".join(parts)
        if len(text) > _MAX_CONTEXT_CHARS:
            # Reserve one character for ellipsis so total length never exceeds the cap.
            text = text[: _MAX_CONTEXT_CHARS - 1] + "…"
        return text

    def is_empty(self) -> bool:
        return (
            not self.terminology_map
            and not self.named_entity_registry
            and not self.chapter_context_summary
        )

    def to_snapshot_dict(self) -> dict:
        """Serialize to a plain dict suitable for JSONB storage."""
        return {
            "terminology": {
                src: {"t": tgt, "h": self.term_hits.get(src, 1)}
                for src, tgt in self.terminology_map.items()
            },
            "entities": {
                name: {**meta, "h": self.entity_hits.get(name, 1)}
                for name, meta in self.named_entity_registry.items()
            },
            "chapter_summary": self.chapter_context_summary,
        }

    @classmethod
    def from_snapshot_dict(cls, data: dict) -> "ConsistencyMemory":
        """Deserialize from JSONB snapshot dict produced by to_snapshot_dict()."""
        terminology_map: Dict[str, str] = {}
        term_hits: Dict[str, int] = {}
        raw_terminology = data.get("terminology")
        for src, val in (raw_terminology if isinstance(raw_terminology, dict) else {}).items():
            if isinstance(val, dict):
                terminology_map[src] = val.get("t", "")
                term_hits[src] = val.get("h", 1)
            else:
                # Legacy string format (migration compatibility).
                terminology_map[src] = str(val)
                term_hits[src] = 1

        named_entity_registry: Dict[str, Dict[str, Any]] = {}
        entity_hits: Dict[str, int] = {}
        raw_entities = data.get("entities")
        for name, meta in (raw_entities if isinstance(raw_entities, dict) else {}).items():
            if isinstance(meta, dict):
                h = meta.pop("h", 1)
                named_entity_registry[name] = meta
                entity_hits[name] = h
            else:
                named_entity_registry[name] = {}
                entity_hits[name] = 1

        return cls(
            terminology_map=terminology_map,
            named_entity_registry=named_entity_registry,
            chapter_context_summary=data.get("chapter_summary", ""),
            term_hits=term_hits,
            entity_hits=entity_hits,
        )

# vortex/core/memory.py

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import json


@dataclass
class MemoryItem:
    id: int
    timestamp: str  # ISO string
    category: str   # e.g., "note", "reminder", "pref"
    text: str


class _SemanticEncoder:
    """
    Optional semantic encoder using sentence-transformers.

    If the library/model is not available, is_available = False and
    MemoryManager will automatically fall back to keyword search.
    """

    def __init__(self, logger=None):
        self.logger = logger
        self.model = None
        self.is_available = False

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception as e:
            if self.logger:
                self.logger.warning(
                    f"Semantic search disabled (sentence-transformers not available): {e}"
                )
            return

        try:
            # Small, fast, good enough
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            self.is_available = True
            if self.logger:
                self.logger.info("Semantic encoder loaded: all-MiniLM-L6-v2")
        except Exception as e:
            if self.logger:
                self.logger.warning(
                    f"Semantic search disabled (model load failed): {e}"
                )
            self.model = None
            self.is_available = False

    def top_similar(
        self,
        query: str,
        items: List[MemoryItem],
        limit: int = 5,
        min_score: float = 0.25,
    ) -> List[MemoryItem]:
        """
        Return up to `limit` items most similar to `query`, using cosine similarity.
        If encoder is not available or anything fails, returns [].
        """
        if not self.is_available or not items or not query.strip():
            return []

        try:
            import numpy as np  # type: ignore
        except Exception:
            if self.logger:
                self.logger.warning("Numpy not available for semantic search; skipping.")
            return []

        try:
            texts = [m.text for m in items]
            doc_emb = self.model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            q_emb = self.model.encode(
                [query],
                convert_to_numpy=True,
                normalize_embeddings=True,
            )[0]

            scores = np.dot(doc_emb, q_emb)  # (N,)
            idxs = np.argsort(scores)[::-1]   # descending
            results: List[MemoryItem] = []
            for idx in idxs:
                if len(results) >= limit:
                    break
                score = float(scores[idx])
                if score < min_score:
                    break
                results.append(items[idx])

            return results
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Semantic search failed at runtime, falling back: {e}")
            return []


class MemoryManager:
    """
    Persistent memory manager using JSON file.

    - add()           -> store a new memory
    - list_recent()   -> latest memories
    - search()        -> hybrid (keyword + semantic)
    - delete_all()    -> clear notes
    - delete_by_id()  -> delete by numeric id
    - delete_by_query()-> delete using semantic/keyword search
    """

    def __init__(self, data_dir: Path, logger=None):
        self.data_dir = data_dir
        self.logger = logger
        self.path = self.data_dir / "memory.json"
        self._memories: List[MemoryItem] = []

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._encoder = _SemanticEncoder(logger=self.logger)

        self._load()

    # ------------------------------------------------------------------ internal

    def _load(self):
        if not self.path.exists():
            if self.logger:
                self.logger.info(f"Memory file not found at {self.path}, starting empty.")
            self._memories = []
            return

        try:
            with self.path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            self._memories = [
                MemoryItem(
                    id=int(item.get("id", i + 1)),
                    timestamp=item.get("timestamp", ""),
                    category=item.get("category", "note"),
                    text=item.get("text", ""),
                )
                for i, item in enumerate(raw)
            ]
            if self.logger:
                self.logger.info(f"Loaded {len(self._memories)} memories from disk.")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to load memory file: {e}")
            self._memories = []

    def _save(self):
        try:
            data = [asdict(m) for m in self._memories]
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to save memory file: {e}")

    # ------------------------------------------------------------------ public: add + list + search

    def add(self, text: str, category: str = "note") -> MemoryItem:
        next_id = (self._memories[-1].id + 1) if self._memories else 1
        item = MemoryItem(
            id=next_id,
            timestamp=datetime.now().isoformat(timespec="seconds"),
            category=category,
            text=text.strip(),
        )
        self._memories.append(item)
        self._save()
        if self.logger:
            self.logger.info(f"Memory added [{item.id}] ({category}): {item.text}")
        return item

    def list_recent(self, limit: int = 5, category: Optional[str] = None) -> List[MemoryItem]:
        items = self._memories
        if category:
            items = [m for m in items if m.category == category]
        return items[-limit:]

    def search(self, query: str, category: Optional[str] = None, limit: int = 5) -> List[MemoryItem]:
        """
        Hybrid search:

        1) Keyword search (substring or all-words).
        2) If no results and semantic encoder is available, semantic search.
        """
        q = query.lower().strip()
        if not q:
            return []

        items = self._memories
        if category:
            items = [m for m in items if m.category == category]

        # 1) keyword / substring / all words
        keyword_results: List[MemoryItem] = []
        if items:
            keyword_results = [m for m in items if q in m.text.lower()]

            if not keyword_results and " " in q:
                words = [w for w in q.split() if w]
                keyword_results = [
                    m for m in items
                    if all(w in m.text.lower() for w in words)
                ]

        if keyword_results:
            return keyword_results[-limit:]

        # 2) semantic fallback
        if self._encoder and self._encoder.is_available:
            semantic_results = self._encoder.top_similar(query, items, limit=limit)
            if semantic_results:
                if self.logger:
                    self.logger.info(
                        f"Semantic memory search used for query '{query}', "
                        f"returned {len(semantic_results)} results."
                    )
                return semantic_results

        if self.logger:
            self.logger.info(f"No memory results for query '{query}'.")
        return []

    # ------------------------------------------------------------------ public: delete

    def delete_all(self, category: Optional[str] = None) -> int:
        """Delete all memories (optionally filtering by category). Returns count."""
        if category:
            remaining = [m for m in self._memories if m.category != category]
            deleted = len(self._memories) - len(remaining)
            self._memories = remaining
        else:
            deleted = len(self._memories)
            self._memories = []

        if deleted:
            self._save()
        if self.logger:
            self.logger.info(f"Deleted {deleted} memories (category={category}).")
        return deleted

    def delete_by_id(self, mem_id: int, category: Optional[str] = None) -> bool:
        """Delete a single memory by id. Returns True if something was deleted."""
        before = len(self._memories)
        if category:
            self._memories = [
                m for m in self._memories
                if not (m.id == mem_id and m.category == category)
            ]
        else:
            self._memories = [m for m in self._memories if m.id != mem_id]

        if len(self._memories) < before:
            self._save()
            if self.logger:
                self.logger.info(f"Deleted memory id={mem_id} (category={category}).")
            return True

        if self.logger:
            self.logger.info(f"No memory found to delete with id={mem_id}.")
        return False

    def delete_by_query(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 1,
    ) -> List[MemoryItem]:
        """
        Delete memories that best match the query (semantic + keyword).
        Returns list of deleted items.
        """
        results = self.search(query, category=category, limit=limit)
        if not results:
            return []

        ids_to_delete = {m.id for m in results}
        deleted_items = [m for m in self._memories if m.id in ids_to_delete]
        self._memories = [m for m in self._memories if m.id not in ids_to_delete]
        self._save()

        if self.logger:
            self.logger.info(
                f"Deleted {len(deleted_items)} memories via query '{query}'. "
                f"IDs: {[m.id for m in deleted_items]}"
            )
        return deleted_items

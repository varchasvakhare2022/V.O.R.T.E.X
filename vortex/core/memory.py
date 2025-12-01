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


class MemoryManager:
    """
    Simple persistent memory manager using a JSON file.

    - add()           -> store a new memory
    - list_recent()   -> get latest memories
    - search()        -> find memories containing some text
    """

    def __init__(self, data_dir: Path, logger=None):
        self.data_dir = data_dir
        self.logger = logger
        self.path = self.data_dir / "memory.json"
        self._memories: List[MemoryItem] = []

        self.data_dir.mkdir(parents=True, exist_ok=True)
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

    # ------------------------------------------------------------------ public

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
        q = query.lower().strip()
        if not q:
            return []

        items = self._memories
        if category:
            items = [m for m in items if m.category == category]

        # simple substring / word match
        results = [m for m in items if q in m.text.lower()]

        if not results and " " in q:
            words = [w for w in q.split() if w]
            results = [
                m for m in items
                if all(w in m.text.lower() for w in words)
            ]

        return results[-limit:]

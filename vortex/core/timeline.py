# vortex/core/timeline.py

"""
Timeline manager for VORTEX.

Phase 1:
- Keep a simple in-memory list of events (time + kind + text)
- Controller can push events, UI can display them
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class TimelineEvent:
    timestamp: datetime
    kind: str      # "user", "system", "note", etc.
    text: str


class TimelineManager:
    def __init__(self):
        self._events: List[TimelineEvent] = []

    def add_event(self, kind: str, text: str) -> TimelineEvent:
        ev = TimelineEvent(timestamp=datetime.now(), kind=kind, text=text)
        self._events.append(ev)
        return ev

    def get_events(self) -> List[TimelineEvent]:
        return list(self._events)

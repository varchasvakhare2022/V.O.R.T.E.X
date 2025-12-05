# vortex/core/command_engine.py

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class CommandType(Enum):
    OPEN_APP = auto()
    CLOSE_APP = auto()
    NOTE_REMEMBER = auto()
    NOTE_QUERY = auto()
    SMALLTALK = auto()
    UNKNOWN = auto()


@dataclass
class ParsedCommand:
    type: CommandType
    raw_text: str
    app_name: Optional[str] = None
    note_text: Optional[str] = None
    message_to_user: str = ""


class CommandEngine:
    """
    Very lightweight rule-based command parser.

    It does NOT try to be an LLM – it just recognises a few patterns:
      - open/close applications
      - remember X
      - what did I tell you / what do you remember
      - otherwise falls back to SMALLTALK / UNKNOWN
    """

    def __init__(self):
        # Logical app names mapped to simple keyword triggers
        self.app_keywords = {
            "notepad": ["notepad", "note pad"],
            "chrome": ["chrome", "google chrome"],
            "edge": ["edge", "microsoft edge"],
            "code": ["vs code", "vscode", "code", "visual studio code"],
            "whatsapp": ["whatsapp", "whats app"],
        }

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def parse(self, text: str) -> ParsedCommand:
        raw = text.strip()
        lowered = raw.lower().strip()

        if not lowered:
            return ParsedCommand(
                type=CommandType.UNKNOWN,
                raw_text=raw,
                message_to_user="",
            )

        # 1) App control
        app_cmd = self._parse_app_command(lowered)
        if app_cmd is not None:
            app_cmd.raw_text = raw
            return app_cmd

        # 2) Memory: explicit queries ("what did I tell you to remember?")
        mem_query = self._parse_memory_query(lowered)
        if mem_query is not None:
            mem_query.raw_text = raw
            return mem_query

        # 3) Memory: remember X / note that X
        mem_store = self._parse_memory_store(lowered, raw)
        if mem_store is not None:
            return mem_store

        # 4) Smalltalk vs unknown
        if lowered.endswith("?"):
            # Any unrecognised question goes to SMALLTALK
            return ParsedCommand(
                type=CommandType.SMALLTALK,
                raw_text=raw,
                message_to_user="",
            )

        # Non-question, non-command → let personality handle
        return ParsedCommand(
            type=CommandType.UNKNOWN,
            raw_text=raw,
            message_to_user="",
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _parse_app_command(self, lowered: str) -> Optional[ParsedCommand]:
        """
        Detects things like:
          - open chrome
          - launch vscode
          - close notepad
          - shut whatsapp
        """
        open_verbs = ("open", "launch", "start", "run")
        close_verbs = ("close", "quit", "exit", "shut", "shut down", "kill")

        tokens = lowered.split()

        if not tokens:
            return None

        first_two = " ".join(tokens[:2])

        is_open = tokens[0] in open_verbs
        is_close = tokens[0] in close_verbs or first_two in close_verbs

        if not (is_open or is_close):
            return None

        # remove the verb ("open", "close", ..) from the beginning
        if first_two in close_verbs:
            remainder = lowered[len(first_two) :].strip()
        else:
            remainder = lowered[len(tokens[0]) :].strip()

        if not remainder:
            return None

        # Try to match an app keyword in the remainder
        app_name = None
        for logical_name, keywords in self.app_keywords.items():
            for kw in keywords:
                if kw in remainder:
                    app_name = logical_name
                    break
            if app_name:
                break

        if not app_name:
            return None

        if is_open:
            msg = f"Opening {app_name} for you."
            return ParsedCommand(
                type=CommandType.OPEN_APP,
                raw_text=lowered,
                app_name=app_name,
                message_to_user=msg,
            )
        else:
            msg = f"Closing {app_name} for you."
            return ParsedCommand(
                type=CommandType.CLOSE_APP,
                raw_text=lowered,
                app_name=app_name,
                message_to_user=msg,
            )

    # ------------------------------------------------------------------ #

    def _parse_memory_query(self, lowered: str) -> Optional[ParsedCommand]:
        """
        Recognises questions ABOUT memory, e.g.:

          - what did i tell you to remember?
          - what did i tell you about my lab?
          - what did i ask you to remember?
          - what do you remember?
          - what are things you noted down?
          - what did i tell you yesterday?

        These should NEVER store new notes.
        """

        # Normalise multiple spaces just a little bit
        text = " ".join(lowered.split())

        query_starts = (
            "what did i tell you to remember",
            "what did i tell you about",
            "what did i ask you to remember",
            "what did i tell you yesterday",
            "what did i tell you last time",
            "what did i tell you earlier",
            "what do you remember",
            "what can you remember",
            "what are things you noted down",
            "what did i tell you",
        )

        for prefix in query_starts:
            if text.startswith(prefix):
                return ParsedCommand(
                    type=CommandType.NOTE_QUERY,
                    raw_text=lowered,
                    message_to_user="Here's what I remember related to that:",
                )

        return None

    # ------------------------------------------------------------------ #

    def _parse_memory_store(self, lowered: str, raw: str) -> Optional[ParsedCommand]:
        """
        Recognises "remember X" / "note that X" / "make a note that X".

        Examples:
          - remember i have an exam at 2 pm on friday
          - remember that my dbms lab is at 4 pm on friday
          - note that i need to go to washroom in 2mins
          - make a note that i have to submit lab file tomorrow
        """

        text = lowered

        # Phrases that mean "store this":
        store_prefixes = (
            "remember that",
            "remember to",
            "remember ",
            "note that",
            "note down that",
            "make a note that",
            "take a note that",
            "note down",
            "take a note",
        )

        note_text = None

        # Case 1: sentence starts with one of the store prefixes
        for prefix in store_prefixes:
            if text.startswith(prefix):
                note_text = text[len(prefix) :].strip()
                break

        # Case 2: "… please remember that X" or "… so remember that X"
        if note_text is None:
            marker = "remember that"
            if marker in text:
                note_text = text.split(marker, 1)[1].strip()

        if note_text is None:
            return None

        # Fallback: if we somehow stripped everything, just store the raw text
        if not note_text:
            note_text = raw

        msg = f"I'll remember that: {note_text}"
        return ParsedCommand(
            type=CommandType.NOTE_REMEMBER,
            raw_text=raw,
            note_text=note_text,
            message_to_user=msg,
        )

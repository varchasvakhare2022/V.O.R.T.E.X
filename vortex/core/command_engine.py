# vortex/core/command_engine.py

"""
CommandEngine: interprets user text (typed or voice) into structured commands.

Phase 1–2:
- Handles opening/closing apps
- Note-taking
- Smalltalk
- Security mode toggles
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional
import datetime


class CommandType(Enum):
    OPEN_APP = auto()
    CLOSE_APP = auto()
    NOTE = auto()
    SMALLTALK = auto()
    SECURITY_MODE = auto()
    NORMAL_MODE = auto()
    UNKNOWN = auto()


@dataclass
class ParsedCommand:
    type: CommandType
    app_name: Optional[str] = None
    note_text: Optional[str] = None
    raw_text: str = ""
    message_to_user: str = ""  # what VORTEX should say as a response


class CommandEngine:
    """
    Phase 1–2 "brain":
    - Maps natural-ish phrases to a ParsedCommand
    - Later we can replace internals with a local LLM while keeping the same interface.
    """

    def __init__(self, owner_name: str = "User"):
        self.owner_name = owner_name

    # ------------- MAIN PARSER -------------

    def parse(self, text: str) -> ParsedCommand:
        lowered = text.lower().strip()

        if not lowered:
            return ParsedCommand(
                type=CommandType.UNKNOWN,
                raw_text=text,
                message_to_user="I didn't catch that. Please repeat.",
            )

        # ---- SECURITY MODE ----
        if "enter security mode" in lowered or "security alert" in lowered:
            return ParsedCommand(
                type=CommandType.SECURITY_MODE,
                raw_text=text,
                message_to_user="Entering security mode. All systems on high alert.",
            )

        if "normal mode" in lowered or "stand down" in lowered:
            return ParsedCommand(
                type=CommandType.NORMAL_MODE,
                raw_text=text,
                message_to_user="Returning to normal operational mode.",
            )

        # ---- CLOSE APP ----
        if any(kw in lowered for kw in ["close", "exit", "shut", "quit"]):
            app_name = self._extract_app_name(lowered)
            if app_name:
                return ParsedCommand(
                    type=CommandType.CLOSE_APP,
                    raw_text=text,
                    app_name=app_name,
                    message_to_user=f"Closing {app_name} for you.",
                )

        # ---- OPEN APP ----
        if any(kw in lowered for kw in ["open", "launch", "start"]):
            app_name = self._extract_app_name(lowered)
            if app_name:
                return ParsedCommand(
                    type=CommandType.OPEN_APP,
                    raw_text=text,
                    app_name=app_name,
                    message_to_user=f"Opening {app_name} for you.",
                )

        # ---- NOTE COMMANDS ----
        # Only treat as note if it DOESN'T look like "notepad"/"note pad"
        if ("note" in lowered or "remember" in lowered) and "note pad" not in lowered:
            note_text = text
            for kw in ["note that", "note this", "note", "remember that", "remember"]:
                if kw in lowered:
                    idx = lowered.find(kw) + len(kw)
                    note_text = text[idx:].strip()
                    break

            return ParsedCommand(
                type=CommandType.NOTE,
                raw_text=text,
                note_text=note_text,
                message_to_user=f"I'll remember that: {note_text}",
            )

        # ---- SMALLTALK / WAKE NAME ----
        if "vortex" in lowered:
            return ParsedCommand(
                type=CommandType.SMALLTALK,
                raw_text=text,
                message_to_user="You called, I'm listening.",
            )

        if any(kw in lowered for kw in ["how are you", "how are u", "are you there"]):
            return ParsedCommand(
                type=CommandType.SMALLTALK,
                raw_text=text,
                message_to_user="Online and fully operational. How can I assist you?",
            )

        # ---- TIME ----
        if any(kw in lowered for kw in ["time is it", "current time"]):
            now = datetime.datetime.now().strftime("%H:%M")
            return ParsedCommand(
                type=CommandType.SMALLTALK,
                raw_text=text,
                message_to_user=f"It is {now} at your location.",
            )

        # ---- UNKNOWN ----
        return ParsedCommand(
            type=CommandType.UNKNOWN,
            raw_text=text,
            message_to_user="I'm still learning. I didn't understand that command yet.",
        )

    # ------------- HELPERS -------------

    def _extract_app_name(self, lowered: str) -> Optional[str]:
        """
        Super simple app name extraction.
        We just look for known app keywords.
        """
        known_apps = {
            "notepad": "notepad",
            "note pad": "notepad",
            "pad": "notepad",
            "text": "notepad",
            "chrome": "chrome",
            "browser": "chrome",
            "code": "code",
            "vs code": "code",
            "visual studio code": "code",
            "whatsapp": "whatsapp",
        }

        for key, app in known_apps.items():
            if key in lowered:
                return app
        return None

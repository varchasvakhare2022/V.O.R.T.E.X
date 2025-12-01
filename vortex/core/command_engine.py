# vortex/core/command_engine.py

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional
import difflib


class CommandType(Enum):
    OPEN_APP = auto()
    CLOSE_APP = auto()
    NOTE = auto()
    ENROLL_VOICE = auto()
    ENROLL_FACE = auto()
    SECURITY_MODE = auto()
    NORMAL_MODE = auto()
    SMALLTALK = auto()
    MEMORY_QUERY = auto()
    UNKNOWN = auto()


@dataclass
class ParsedCommand:
    type: CommandType
    raw_text: str
    app_name: Optional[str] = None
    note_text: Optional[str] = None
    message_to_user: str = ""
    memory_action: Optional[str] = None   # "recent" / "search"
    memory_query: Optional[str] = None    # search text


class CommandEngine:
    """
    Lightweight, rule-based intent parser for VORTEX.
    No ML, no APIs – just clever pattern + fuzzy matching.
    """

    def __init__(self, owner_name: str = "User"):
        self.owner_name = owner_name

        # Words that often appear but don't change intent
        self.filler_prefixes = [
            "vortex", "jarvis", "hey vortex", "hey jarvis",
            "please", "can you", "could you", "would you",
            "will you", "could you please", "can you please",
            "i want to", "i wanna", "i would like to",
            "try", "just", "maybe", "kindly",
        ]

        # App synonyms; normalized to logical app names
        self.known_apps = {
            "notepad": "notepad",
            "note pad": "notepad",
            "pad": "notepad",
            "text": "notepad",
            "notes": "notepad",

            "chrome": "chrome",
            "browser": "chrome",
            "google": "chrome",

            "edge": "edge",
            "microsoft edge": "edge",
            "ms edge": "edge",

            "whatsapp": "whatsapp",
            "whats app": "whatsapp",

            "code": "code",
            "vs code": "code",
            "visual studio code": "code",
        }

    # ------------------------------------------------------------------ public

    def parse(self, text: str) -> ParsedCommand:
        raw = text.strip()
        if not raw:
            return ParsedCommand(
                type=CommandType.UNKNOWN,
                raw_text="",
                message_to_user="I didn't hear anything to process."
            )

        lowered = raw.lower()
        cleaned = self._strip_filler(lowered).strip()

        # Voice / face enrollment
        if any(kw in cleaned for kw in ["enrol my voice", "enroll my voice", "register my voice", "voice enrollment"]):
            return ParsedCommand(
                type=CommandType.ENROLL_VOICE,
                raw_text=raw,
                message_to_user="Starting voice enrollment procedure."
            )

        if any(kw in cleaned for kw in ["enrol my face", "enroll my face", "register my face", "face enrollment"]):
            return ParsedCommand(
                type=CommandType.ENROLL_FACE,
                raw_text=raw,
                message_to_user="Starting face enrollment procedure."
            )

        # Security / normal mode
        if "security mode" in cleaned or "go secure" in cleaned or "lockdown" in cleaned:
            return ParsedCommand(
                type=CommandType.SECURITY_MODE,
                raw_text=raw,
                message_to_user="Entering security mode."
            )

        if "normal mode" in cleaned or "stand down" in cleaned or "back to normal" in cleaned:
            return ParsedCommand(
                type=CommandType.NORMAL_MODE,
                raw_text=raw,
                message_to_user="Returning to normal operational mode."
            )

        # Open / close apps
        if self._is_open_intent(cleaned):
            app_name = self._extract_app_name(cleaned)
            if app_name:
                return ParsedCommand(
                    type=CommandType.OPEN_APP,
                    raw_text=raw,
                    app_name=app_name,
                    message_to_user=f"Opening {app_name} for you."
                )

        if self._is_close_intent(cleaned):
            if "system" in cleaned and not self._extract_app_name(cleaned):
                app_name = "code"
            else:
                app_name = self._extract_app_name(cleaned)

            if app_name:
                return ParsedCommand(
                    type=CommandType.CLOSE_APP,
                    raw_text=raw,
                    app_name=app_name,
                    message_to_user=f"Closing {app_name} for you."
                )

        # Notes / memory (add)
        if self._looks_like_note(cleaned):
            note = self._extract_note_text(cleaned, original=raw)
            if note:
                return ParsedCommand(
                    type=CommandType.NOTE,
                    raw_text=raw,
                    note_text=note,
                    message_to_user=f"I'll remember that: {note}"
                )

        # Memory queries
        if self._looks_like_memory_query(cleaned):
            action, query = self._parse_memory_query(cleaned, raw)
            return ParsedCommand(
                type=CommandType.MEMORY_QUERY,
                raw_text=raw,
                memory_action=action,
                memory_query=query,
                message_to_user=""
            )

        # Smalltalk / chitchat
        if self._looks_like_smalltalk(cleaned):
            return ParsedCommand(
                type=CommandType.SMALLTALK,
                raw_text=raw,
                message_to_user="",  # personality will generate reply
            )

        # Fallback
        return ParsedCommand(
            type=CommandType.UNKNOWN,
            raw_text=raw,
            message_to_user="I'm still learning. I didn't understand that command yet."
        )

    # ------------------------------------------------------------------ helpers

    def _strip_filler(self, text: str) -> str:
        result = text
        changed = True
        while changed:
            changed = False
            for prefix in self.filler_prefixes:
                if result.startswith(prefix + " "):
                    result = result[len(prefix):].lstrip()
                    changed = True
        return result

    def _is_open_intent(self, cleaned: str) -> bool:
        open_words = [
            "open", "start", "launch", "run", "fire up",
            "bring up", "pull up", "show", "go to"
        ]
        return any(w in cleaned for w in open_words)

    def _is_close_intent(self, cleaned: str) -> bool:
        close_words = [
            "close", "quit", "exit", "shut", "kill",
            "terminate", "stop"
        ]
        return any(w in cleaned for w in close_words)

    def _extract_app_name(self, lowered: str) -> Optional[str]:
        # 1) Exact substring match
        for key, app in self.known_apps.items():
            if key in lowered:
                return app

        # 2) Fuzzy match on individual words
        words = lowered.replace(".", " ").split()
        keys = list(self.known_apps.keys())

        for word in words:
            if len(word) < 3:
                continue
            close = difflib.get_close_matches(word, keys, n=1, cutoff=0.6)
            if close:
                return self.known_apps[close[0]]

        return None

    def _looks_like_note(self, cleaned: str) -> bool:
        note_triggers = [
            "note that", "remember that", "remember to",
            "make a note", "take a note", "i need to remember",
            "remind me to", "remind me that",
        ]
        return any(t in cleaned for t in note_triggers)

    def _extract_note_text(self, cleaned: str, original: str) -> str:
        triggers = [
            "note that", "remember that", "remember to",
            "make a note", "take a note", "i need to remember",
            "remind me to", "remind me that",
        ]

        lowered_orig = original.lower()
        for trig in triggers:
            idx = lowered_orig.find(trig)
            if idx != -1:
                start = idx + len(trig)
                return original[start:].strip(" .")

        return original.strip()

    def _looks_like_memory_query(self, cleaned: str) -> bool:
        triggers = [
            "what did i tell you to remember",
            "what did i ask you to remember",
            "what do you remember",
            "show my notes",
            "list my notes",
            "show my reminders",
            "list my reminders",
            "what are my notes",
            "what reminders do i have",
        ]
        if any(t in cleaned for t in triggers):
            return True
        if cleaned.startswith("do you remember"):
            return True
        return False

    def _parse_memory_query(self, cleaned: str, original: str):
        if cleaned.startswith("do you remember"):
            lowered_orig = original.lower()
            key = "do you remember"
            idx = lowered_orig.find(key)
            rest = original[idx + len(key):].strip(" ?.")
            return "search", rest
        # default: list recent notes
        return "recent", ""

    def _looks_like_smalltalk(self, cleaned: str) -> bool:
        smalltalk_phrases = [
            "how are you",
            "how's it going",
            "what's up",
            "are you there",
            "are you online",
            "are you working",
            "are you fully operational",
            "are you fully functional",
            "are you fine",
            "are you ok",
            "who are you",
            "what can you do",
        ]
        return any(p in cleaned for p in smalltalk_phrases)

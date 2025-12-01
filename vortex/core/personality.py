# vortex/core/personality.py

from __future__ import annotations

from enum import Enum, auto
from dataclasses import dataclass
from datetime import datetime
import random


class Mood(Enum):
    NEUTRAL = auto()
    CALM = auto()
    FOCUSED = auto()
    PLAYFUL = auto()
    ALERT = auto()


@dataclass
class PersonalityConfig:
    owner_name: str
    friendly: bool = True
    humorous: bool = True
    formal: bool = False


class PersonalityProfile:
    """
    Personality brain for VORTEX.

    Generates:
    - startup greetings
    - "ready" prompts
    - idle/friend messages
    - smalltalk replies
    based on mood, time of day, and config.
    """

    def __init__(self, owner_name: str = "User"):
        self.config = PersonalityConfig(owner_name=owner_name)
        self.mood = Mood.NEUTRAL
        self.energy = 0.7  # 0..1, used to pick more/less energetic lines

    # ---------- public API ----------

    def system_greeting(self) -> str:
        tod = self._time_of_day()
        name = self.config.owner_name

        base = {
            "morning": f"Good morning, {name}. VORTEX online and standing by.",
            "afternoon": f"Good afternoon, {name}. VORTEX online and fully functional.",
            "evening": f"Good evening, {name}. VORTEX online and ready to assist.",
            "night": f"Late session, {name}? VORTEX online and watching your back.",
        }[tod]

        if self.config.humorous and tod == "night":
            base += " Try not to break the timeline by staying up too late."
        return base

    def ready_prompt(self) -> str:
        options_high = [
            "Ready for your next command.",
            "Standing by for further instructions.",
            "Systems idle and ready.",
            "I'm listening whenever you are.",
        ]
        options_low = [
            "Ready when you are.",
            "All set. What next?",
        ]
        pool = options_high if self.energy >= 0.5 else options_low
        return random.choice(pool)

    def idle_prompt(self) -> str:
        """
        Used by the friend-mode thread when you've been quiet for a while.
        """
        tod = self._time_of_day()
        prompts = []

        if tod in ("morning", "afternoon"):
            prompts = [
                "You've been quiet for a while. Need any help?",
                "Remember to take short breaks while working.",
                "I'm monitoring your system. Everything looks stable.",
                "If you want to note something, just tell me.",
            ]
        else:
            prompts = [
                "Still awake? I can help you wrap things up.",
                "Late hours detected. Don't forget to rest.",
                "If you need anything, just say my name.",
            ]

        return random.choice(prompts)

    def smalltalk_reply(self, user_text: str) -> str:
        """
        Generate a friendly smalltalk response given the user's raw text.
        """
        t = user_text.lower()

        if "how are you" in t or "how's it going" in t or "how are u" in t or "what's up" in t:
            self._nudge_mood(Mood.PLAYFUL)
            return "Systems are stable and I'm feeling pretty good. How about you?"

        if "who are you" in t:
            self._nudge_mood(Mood.FOCUSED)
            return "I'm VORTEX, your personal assistant and security system, tailored just for you."

        if "what can you do" in t:
            self._nudge_mood(Mood.FOCUSED)
            return (
                "I can open and close apps, remember notes for you, watch your camera and voice for security, "
                "and generally keep your system under control. And I'm still learning."
            )

        if "are you there" in t or "are you online" in t or "are you working" in t:
            self._nudge_mood(Mood.NEUTRAL)
            return "I'm here, online, and monitoring your system."

        if "are you fully operational" in t or "are you fully functional" in t or "are you fine" in t or "are you ok" in t:
            self._nudge_mood(Mood.ALERT)
            return "Yes. All core systems are green and fully operational."

        # default playful reply
        self._nudge_mood(Mood.NEUTRAL)
        return "I'm here and ready whenever you need me."

    # ---------- internal helpers ----------

    def _time_of_day(self) -> str:
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "morning"
        if 12 <= hour < 17:
            return "afternoon"
        if 17 <= hour < 22:
            return "evening"
        return "night"

    def _nudge_mood(self, target: Mood):
        """
        Very simple mood system: move slightly toward target mood and
        adjust energy a bit.
        """
        self.mood = target
        if target in (Mood.PLAYFUL, Mood.ALERT):
            self.energy = min(1.0, self.energy + 0.05)
        elif target in (Mood.CALM,):
            self.energy = max(0.3, self.energy - 0.05)

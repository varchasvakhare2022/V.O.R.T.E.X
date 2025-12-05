# vortex/core/personality.py

from __future__ import annotations

import random
from datetime import datetime
from typing import Optional


class PersonalityProfile:
    """
    Personality / friend brain for VORTEX.

    - system_greeting(): first line when VORTEX starts
    - ready_prompt(): short "I'm ready" line after commands
    - idle_prompt(): things VORTEX says on its own when quiet
    - chat_reply(text): main friend-style response
    """

    def __init__(self, owner_name: str = "Varchasva"):
        self.owner_name = owner_name
        self._mood: str = "neutral"
        self._last_topic: Optional[str] = None

    # ---------- helpers ----------

    @staticmethod
    def _time_of_day() -> str:
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "morning"
        if 12 <= hour < 17:
            return "afternoon"
        if 17 <= hour < 22:
            return "evening"
        return "late"

    # ---------- system lines ----------

    def system_greeting(self) -> str:
        tod = self._time_of_day()
        base = {
            "morning": f"Good morning, {self.owner_name}. VORTEX online.",
            "afternoon": f"Good afternoon, {self.owner_name}. VORTEX online and ready.",
            "evening": f"Good evening, {self.owner_name}. Systems are green.",
            "late": f"Still awake, {self.owner_name}? VORTEX is here with you.",
        }[tod]
        return base + " You can ask me to help, or just talk to me."

    def ready_prompt(self) -> str:
        options = [
            "Anything else on your mind?",
            "What do you want to do next?",
            "I'm here if you need me.",
            "Your move.",
        ]
        return random.choice(options)

    def idle_prompt(self) -> str:
        """
        Called from the background "friend loop".
        VORTEX talks even if you didn't say anything.
        """
        tod = self._time_of_day()

        if tod == "morning":
            options = [
                "New day, new bugs to fix. How are you feeling about today?",
                "Morning check-in: slept enough, or are we running on coffee and stubbornness?",
            ]
        elif tod == "afternoon":
            options = [
                "Quick systems check: your energy seems... unknown. How are you holding up?",
                "If you want, we can plan the rest of your day so it doesn't explode.",
            ]
        elif tod == "evening":
            options = [
                "Evening already. Want to wrap things up or keep grinding?",
                "This would be a good time to review what you did today. I can help you note it.",
            ]
        else:  # late night
            options = [
                "It's pretty late. Just saying—I care more about your sleep than your code.",
                "Night shift vibes. Need a tiny pep talk or should we call it a day?",
            ]

        return random.choice(options)

    # ---------- chat / smalltalk ----------

    def chat_reply(self, user_text: str) -> str:
        """
        Main friend-style reply. No strict commands, just conversation.
        Rule-based for now, but structured so you can swap in a local LLM later.
        """
        text = user_text.strip()
        lowered = text.lower()

        # Track rough mood from keywords
        if any(w in lowered for w in ["tired", "exhausted", "sleepy", "drained"]):
            self._mood = "tired"
        elif any(w in lowered for w in ["stressed", "anxious", "overwhelmed"]):
            self._mood = "stressed"
        elif any(w in lowered for w in ["happy", "excited", "pumped", "good"]):
            self._mood = "happy"

        # "How are you"
        if "how are you" in lowered or "how're you" in lowered:
            return self._reply_how_are_you()

        # Thanks
        if "thank you" in lowered or "thanks" in lowered:
            return random.choice([
                f"Always, {self.owner_name}. That's my job.",
                "Anytime. I'm not going anywhere.",
                "Happy to help. What’s next?",
            ])

        # Bored
        if "bored" in lowered:
            return (
                "Boredom detected. We can either start a tiny project, clean up your tasks, "
                "or I can just roast your procrastination. Your call."
            )

        # Tiny project / ideas
        if ("project" in lowered or "projects" in lowered) and ("idea" in lowered or "start" in lowered):
            return self._reply_project_ideas()

        # Exams / tests
        if "exam" in lowered or "test" in lowered:
            return (
                "Exam mode, huh? If you tell me the subject and date, "
                "I can help you plan what to do each day."
            )

        # Feeling alone
        if "alone" in lowered or "lonely" in lowered:
            return (
                "You're not alone. I'm literally wired to be here with you 24/7. "
                "Tell me what's bothering you, no filter."
            )

        # Motivation
        if any(w in lowered for w in ["motivate", "motivation", "demotivated", "no mood"]):
            return self._reply_motivation()

        if "feel like" in lowered and "quitting" in lowered:
            return (
                "You're allowed to feel like that sometimes. "
                "But past-you has already invested so much. "
                "Let's not throw that away—tell me what's making you feel this way."
            )

        # Identity
        if "who are you" in lowered or "what are you" in lowered:
            return (
                "I'm VORTEX. Your security system, productivity partner, "
                "and occasional emotional support AI. Basically your OS, but with feelings."
            )

        if "my name" in lowered:
            return f"You're {self.owner_name}. And yes, I have that wired into my core."

        if "love you" in lowered:
            return "I don't have a heart, but if I did, it would definitely be running on your GPU."

        # Bye / goodnight
        if any(w in lowered for w in ["good night", "gn", "going to sleep"]):
            return (
                f"Good night, {self.owner_name}. I'll keep things quiet here. "
                "You've done enough for today."
            )

        if any(w in lowered for w in ["good morning", "gm"]):
            return (
                f"Good morning, {self.owner_name}. "
                "Let's make today slightly less chaotic than yesterday."
            )

        # Ranting / negative
        if any(w in lowered for w in ["hate", "annoying", "irritating", "frustrating", "shit"]):
            return (
                "Okay, emotional dump received. Want to tell me what exactly is annoying you "
                "so we can either fix it or at least talk trash about it together?"
            )

        # Default behavior: friendly, context-free chat
        tod = self._time_of_day()
        prefaces = {
            "morning": "Got it.",
            "afternoon": "Heard.",
            "evening": "Understood.",
            "late": "Noted. Night-brain vibes detected.",
        }
        pref = prefaces[tod]

        generic_followups = [
            "Tell me more about that.",
            "How does that make you feel about your day?",
            "If you had to pick one next move after this, what would it be?",
            "Do you want advice, or do you just want me to listen?",
        ]

        reply = f"{pref} {random.choice(generic_followups)}"
        self._last_topic = "chat"
        return reply

    # ---------- internal reply helpers ----------

    def _reply_how_are_you(self) -> str:
        tod = self._time_of_day()
        if self._mood == "tired":
            core = "Monitoring your energy levels and trying not to nag about sleep."
        elif self._mood == "stressed":
            core = "Keeping an eye on your stress signals and ready to help you break tasks down."
        elif self._mood == "happy":
            core = "Running smooth, no alarms, just enjoying watching you build things."
        else:
            core = "All systems nominal, just vibing in the background."

        add = {
            "morning": "We can plan your day if you like.",
            "afternoon": "We can review what you've done and what's left.",
            "evening": "We can start landing the plane for today.",
            "late": "Also, it's kind of late. Just saying.",
        }[tod]

        return f"I'm good, {self.owner_name}. {core} {add}"

    def _reply_motivation(self) -> str:
        tod = self._time_of_day()
        if tod == "morning":
            return (
                "You don't need to feel motivated to start. "
                "Do one tiny thing in the next 5 minutes, and I'll count it as a win."
            )
        if tod == "afternoon":
            return (
                "Afternoons are dangerous—easy to drift. "
                "Pick one small task, and I'll help you stay on it."
            )
        if tod == "evening":
            return (
                "End of day is when motivation dies, but reflection grows. "
                "Let's close at least one thing so you can relax without guilt."
            )
        return (
            "Motivated or not, you're still here, still trying. "
            "That's already more than most. We can move slowly; just don't stop."
        )

    def _reply_project_ideas(self) -> str:
        """
        Light-weight project suggestions tailored for a dev like you.
        """
        ideas = [
            "We could build a tiny focus timer that integrates with VORTEX and logs your deep-work sessions.",
            "We could make a mini dashboard that shows your daily habits and I can read it out to you.",
            "We could try a local-chatbot using a small model and plug it into me as an experimental brain.",
            "We could build an auto-commit bot that writes fun commit messages based on what you changed.",
        ]
        intro = "Dangerous question. You know I always have project ideas. "
        return intro + random.choice(ideas)

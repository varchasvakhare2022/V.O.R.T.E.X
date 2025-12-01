# vortex/controller.py

"""
VortexController:
- Connects UI, CommandEngine, TTSService, Timeline, and logging.
- Handles app launching.
- Friend-mode chatter (uses signals so GUI updates are thread-safe).
"""

from __future__ import annotations

import subprocess
import threading
import random
import time
from typing import Optional

from PyQt6 import QtCore

from .ui import VortexWindow, VortexTheme
from .core.command_engine import CommandEngine, CommandType
from .core.tts_service import TTSService
from .core.logger import setup_logging
from .core.timeline import TimelineManager


class VortexController(QtCore.QObject):
    system_message = QtCore.pyqtSignal(str)
    user_message = QtCore.pyqtSignal(str)
    timeline_entry = QtCore.pyqtSignal(str)

    def __init__(self, window: VortexWindow, owner_name: str = "Varchasva"):
        super().__init__()
        self.window = window
        self.owner_name = owner_name

        self.logger = setup_logging()
        self.command_engine = CommandEngine(owner_name=owner_name)
        self.tts = TTSService()
        self.timeline = TimelineManager()

        self._friend_mode_running = True
        self._friend_thread: Optional[threading.Thread] = None

        # Connect signals to UI slots (thread-safe)
        self.system_message.connect(self.window.append_system_message_animated)
        self.user_message.connect(self.window.append_user_command)
        self.timeline_entry.connect(self.window.add_timeline_entry)

        # Connect UI to controller
        self.window.command_entered.connect(self.handle_user_command)

        # Start friend chatter
        self._start_friend_mode_thread()

        # Initial greeting
        greet = f"VORTEX online. Welcome back, {self.owner_name}."
        self._emit_system_message(greet)
        self.window.set_status("IDLE")
        self._add_timeline("system", greet)

    # ---------- Command handling ----------

    @QtCore.pyqtSlot(str)
    def handle_user_command(self, text: str):
        self.logger.info(f"User command: {text}")
        self._add_timeline("user", text)

        parsed = self.command_engine.parse(text)

        if parsed.type == CommandType.OPEN_APP and parsed.app_name:
            self._handle_open_app(parsed.app_name, parsed.message_to_user)

        elif parsed.type == CommandType.NOTE and parsed.note_text:
            self.logger.info(f"Note stored: {parsed.note_text}")
            self._add_timeline("note", parsed.note_text)
            self._emit_system_message(parsed.message_to_user)

        elif parsed.type == CommandType.SECURITY_MODE:
            self.window.set_theme(VortexTheme.SECURITY)
            self.window.set_status("SECURITY MODE")
            self._emit_system_message(parsed.message_to_user)
            self._add_timeline("security", "Entered security mode")

        elif parsed.type == CommandType.NORMAL_MODE:
            self.window.set_theme(VortexTheme.NORMAL)
            self.window.set_status("IDLE")
            self._emit_system_message(parsed.message_to_user)
            self._add_timeline("security", "Returned to normal mode")

        elif parsed.type == CommandType.SMALLTALK:
            self._emit_system_message(parsed.message_to_user)
            self._add_timeline("smalltalk", parsed.message_to_user)

        elif parsed.type == CommandType.UNKNOWN:
            self._emit_system_message(parsed.message_to_user)
            self._add_timeline("unknown", parsed.raw_text)

    # ---------- App launching (Phase 1) ----------

    def _handle_open_app(self, app_name: str, message: str):
        self._emit_system_message(message)
        self._add_timeline("action", f"Opening app: {app_name}")

        app_map = {
            "notepad": ["notepad.exe"],
            "chrome": ["chrome.exe"],
            "code": ["code.exe"],
            "whatsapp": ["whatsapp.exe"],  # adjust if needed
        }

        cmd = app_map.get(app_name)
        if not cmd:
            msg = "I don't know how to open that application yet."
            self._emit_system_message(msg)
            self._add_timeline("error", msg)
            return

        try:
            subprocess.Popen(cmd)
            self.logger.info(f"Opened application: {app_name} ({cmd})")
        except Exception as e:
            err = f"I tried to open {app_name} but something went wrong."
            self.logger.error(f"Failed to open {app_name}: {e}")
            self._emit_system_message(err)
            self._add_timeline("error", err)

    # ---------- Friend mode chatter ----------

    def _start_friend_mode_thread(self):
        def friend_loop():
            while self._friend_mode_running:
                delay = random.randint(60, 180)  # 1–3 minutes
                time.sleep(delay)
                msg = random.choice(
                    [
                        "You've been quiet for a while. Need any help?",
                        "Remember to take short breaks while working.",
                        "I'm monitoring your system. Everything looks stable.",
                        "If you want to note something, just tell me.",
                    ]
                )
                self._emit_system_message(msg)
                self._add_timeline("friend", msg)

        self._friend_thread = threading.Thread(target=friend_loop, daemon=True)
        self._friend_thread.start()

    # ---------- Utility ----------

    def _emit_system_message(self, text: str):
        # GUI update through signal
        self.system_message.emit(text)
        # Speak
        self.tts.speak(text)
        self.logger.info(f"System message: {text}")

    def _add_timeline(self, kind: str, text: str):
        ev = self.timeline.add_event(kind, text)
        pretty = f"[{ev.timestamp.strftime('%H:%M:%S')}] ({kind}) {text}"
        self.timeline_entry.emit(pretty)
        # Logged already via logger elsewhere; optional extra log:
        # self.logger.info(f"Timeline: {pretty}")

    def shutdown(self):
        self._friend_mode_running = False
        self.tts.shutdown()
        self.logger.info("VORTEX shutting down.")

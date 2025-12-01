# vortex/controller.py

"""
VortexController:
- Connects UI, CommandEngine, TTSService, Timeline, logging, and now:
- AudioManager + STTService for voice commands (Phase 2A).
"""

from __future__ import annotations

import subprocess
import threading
import random
import time
import psutil

from typing import Optional

from PyQt6 import QtCore

from .ui import VortexWindow, VortexTheme
from .core.command_engine import CommandEngine, CommandType
from .core.tts_service import TTSService
from .core.logger import setup_logging
from .core.timeline import TimelineManager
from .core.audio_manager import AudioManager
from .core.stt_service import STTService


class VortexController(QtCore.QObject):
    system_message = QtCore.pyqtSignal(str)
    user_message = QtCore.pyqtSignal(str)
    timeline_entry = QtCore.pyqtSignal(str)

    voice_command_ready = QtCore.pyqtSignal(str)   # text recognized from voice

    def __init__(self, window: VortexWindow, owner_name: str = "Varchasva"):
        super().__init__()
        self.window = window
        self.owner_name = owner_name

        self.logger = setup_logging()
        self.command_engine = CommandEngine(owner_name=owner_name)
        self.tts = TTSService()
        self.timeline = TimelineManager()

        self.audio_manager = AudioManager()
        self.stt_service = STTService(model_size="tiny", device="cpu", compute_type="int8")

        self._friend_mode_running = True
        self._friend_thread: Optional[threading.Thread] = None

        # Connect signals to UI slots (thread-safe)
        self.system_message.connect(self.window.append_system_message_animated)
        self.user_message.connect(self.window.append_user_command)
        self.timeline_entry.connect(self.window.add_timeline_entry)

        # UI → controller
        self.window.command_entered.connect(self.handle_user_command)
        self.window.voice_listen_requested.connect(self.start_voice_capture)

        # Voice pipeline: recognized text -> handle as command
        self.voice_command_ready.connect(self._handle_voice_command_text)

        # Start friend chatter
        self._start_friend_mode_thread()

        # Initial greeting
        greet = f"VORTEX online. Welcome back, {self.owner_name}."
        self._emit_system_message(greet)
        self.window.set_status("IDLE")
        self._add_timeline("system", greet)

    # ---------- Text command handling (keyboard) ----------

    @QtCore.pyqtSlot(str)
    def handle_user_command(self, text: str):
        self.logger.info(f"User command (typed): {text}")
        self._add_timeline("user", text)
        self._process_command(text)

    # ---------- Voice capture + STT ----------

    @QtCore.pyqtSlot()
    def start_voice_capture(self):
        """
        Called when UI requests listening (Ctrl+Space).
        Spawns a background thread to record and transcribe.
        """
        self.logger.info("Voice capture requested.")
        # Run recording + STT in a worker thread
        worker = threading.Thread(target=self._record_and_transcribe, daemon=True)
        worker.start()

    def _record_and_transcribe(self):
        try:
            self.logger.info("Recording voice phrase...")
            audio, sr = self.audio_manager.record_phrase(duration_sec=4.0)
            self.logger.info("Recording finished, running STT...")
            text = self.stt_service.transcribe(audio, sample_rate=sr)
            text = text.strip()
            self.logger.info(f"STT result: '{text}'")
        except Exception as e:
            self.logger.error(f"Voice capture/STT failed: {e}")
            self._emit_system_message("I had trouble understanding your voice input.")
            self.window.set_status("IDLE")
            return

        if not text:
            self._emit_system_message("I didn't catch anything from the microphone.")
            self.window.set_status("IDLE")
            return

        # Emit signal back to Qt main thread
        self.voice_command_ready.emit(text)

    @QtCore.pyqtSlot(str)
    def _handle_voice_command_text(self, text: str):
        """
        Runs in Qt thread; we now have recognized text from voice.
        Treat it like a user command, but mark as [VOICE].
        """
        display_text = f"[voice] {text}"
        self.user_message.emit(display_text)
        self._add_timeline("voice", text)
        self.window.set_status("IDLE")
        self._process_command(text)

    # ---------- Shared command processing ----------

    def _process_command(self, text: str):
        parsed = self.command_engine.parse(text)

        if parsed.type == CommandType.OPEN_APP and parsed.app_name:
            self._handle_open_app(parsed.app_name, parsed.message_to_user)
        
        elif parsed.type == CommandType.CLOSE_APP and parsed.app_name:
            self._handle_close_app(parsed.app_name, parsed.message_to_user)

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

    # ---------- App launching ----------

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

    def _handle_close_app(self, app_name: str, message: str):
        self._emit_system_message(message)
        self._add_timeline("action", f"Closing app: {app_name}")

        # Map logical names to process executable names (case-insensitive)
        proc_map = {
            "notepad": ["notepad.exe"],
            "chrome": ["chrome.exe"],
            "code": ["code.exe", "Code.exe"],
            "whatsapp": ["whatsapp.exe"],
        }

        targets = proc_map.get(app_name)
        if not targets:
            msg = "I don't know how to close that application yet."
            self._emit_system_message(msg)
            self._add_timeline("error", msg)
            return

        # Make everything lowercase for comparison
        targets_lower = [t.lower() for t in targets]

        killed_any = False
        for proc in psutil.process_iter(attrs=["name", "pid"]):
            try:
                name = proc.info["name"]
                if not name:
                    continue
                if name.lower() in targets_lower:
                    proc.terminate()
                    killed_any = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if killed_any:
            self.logger.info(f"Closed application: {app_name}")
        else:
            msg = f"I couldn't find any running instance of {app_name}."
            self._emit_system_message(msg)
            self._add_timeline("info", msg)



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
        self.system_message.emit(text)
        self.tts.speak(text)
        self.logger.info(f"System message: {text}")

    def _add_timeline(self, kind: str, text: str):
        ev = self.timeline.add_event(kind, text)
        pretty = f"[{ev.timestamp.strftime('%H:%M:%S')}] ({kind}) {text}"
        self.timeline_entry.emit(pretty)

    def shutdown(self):
        self._friend_mode_running = False
        self.tts.shutdown()
        self.logger.info("VORTEX shutting down.")

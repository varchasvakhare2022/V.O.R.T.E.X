# vortex/controller.py

"""
VortexController:
- Connects UI, CommandEngine, TTSService, Timeline, logging
- AudioManager + STTService for voice commands
- IdentityManager for voice + face verification
- CameraMonitor for camera-block security
- WakeWordListener (Porcupine) for "Jarvis" wake word
- Friend-mode chatter
"""

from __future__ import annotations

import subprocess
import threading
import random
import time
from typing import Optional
from pathlib import Path

import psutil
from PyQt6 import QtCore

from .ui import VortexWindow, VortexTheme
from .core.command_engine import CommandEngine, CommandType
from .core.tts_service import TTSService
from .core.logger import setup_logging
from .core.timeline import TimelineManager
from .core.audio_manager import AudioManager
from .core.stt_service import STTService
from .core.identity import IdentityManager
from .core.camera_monitor import CameraMonitor
from .core.wake_word import WakeWordListener


class VortexController(QtCore.QObject):
    system_message = QtCore.pyqtSignal(str)
    user_message = QtCore.pyqtSignal(str)
    timeline_entry = QtCore.pyqtSignal(str)

    voice_command_ready = QtCore.pyqtSignal(str)
    wake_word_detected = QtCore.pyqtSignal()

    def __init__(self, window: VortexWindow, owner_name: str = "Varchasva"):
        super().__init__()
        self.window = window
        self.owner_name = owner_name

        self.logger = setup_logging()
        self.command_engine = CommandEngine(owner_name=owner_name)
        self.tts = TTSService()
        self.timeline = TimelineManager()

        self.audio_manager = AudioManager()
        # use tiny.en for speed + English accuracy
        self.stt_service = STTService(model_size="tiny.en", device="cpu", compute_type="int8")

        self.identity = IdentityManager(
            audio_manager=self.audio_manager,
            logger=self.logger,
            data_dir=Path(__file__).resolve().parents[1] / "data",
        )

        # Camera security
        self.camera_locked: bool = False
        self.camera_monitor = CameraMonitor(
            identity_manager=self.identity,
            logger=self.logger,
            callback_on_blocked=self._camera_blocked,
            callback_on_restored=self._camera_restored,
        )

        # Only allow one voice recording at a time
        self._recording_lock = threading.Lock()

        # Friend mode chatter
        self._friend_mode_running = True
        self._friend_thread: Optional[threading.Thread] = None

        # Connect signals to UI (thread-safe)
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

        # Start camera monitoring
        self.camera_monitor.start(camera_index=0)

        # Initial greeting
        greet = f"VORTEX online. Welcome back, {self.owner_name}."
        self._emit_system_message(greet)
        self.window.set_status("IDLE")
        self._add_timeline("system", greet)

        # Wake word listener (Porcupine) -----------------------
        PORCUPINE_ACCESS_KEY = "h2cmEG5UAD2TDYKeQmxEXlbKGGa8wuElX6ZwBhZq3lOvF1XWvfKEJw=="  # <- replace with your real key

        if PORCUPINE_ACCESS_KEY:
            self.wake_listener = WakeWordListener(
                logger=self.logger,
                on_detect=lambda: self.wake_word_detected.emit(),
                keyword="jarvis",          # built-in Porcupine keyword
                access_key=PORCUPINE_ACCESS_KEY,
            )
            self.wake_word_detected.connect(self._on_wake_word)
            self.wake_listener.start()
            self.system_message.emit('Wake word online. Say "Jarvis" to wake me.')
            self._add_timeline("wake", "Wake word listener started")
        else:
            self.wake_listener = None
            self.system_message.emit("Wake word disabled (no Porcupine access key).")
            self._add_timeline("wake", "Wake word disabled (no access key)")

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
        Called when UI requests listening (Ctrl+Space) OR wake word fires.
        Spawns a background thread to record and transcribe, but only if
        we're not already recording.
        """
        if self._recording_lock.locked():
            self.logger.info("Voice capture requested but a recording is already in progress. Ignoring.")
            return

        self.logger.info("Voice capture requested.")

        # Pause wake listener while we record, to avoid mic conflicts
        try:
            if hasattr(self, "wake_listener") and self.wake_listener is not None:
                self.wake_listener.stop()
        except Exception as e:
            self.logger.error(f"Failed to stop wake listener: {e}")

        worker = threading.Thread(target=self._record_and_transcribe, daemon=True)
        worker.start()

    def _record_and_transcribe(self):
        with self._recording_lock:
            try:
                if self.camera_locked:
                    self._emit_system_message("Camera blocked. Ignoring command for security.")
                    return

                self.logger.info("Recording voice phrase...")
                # 3 seconds is usually enough for a short command
                audio, sr = self.audio_manager.record_phrase(duration_sec=3.0)
                self.logger.info("Recording finished, verifying identity...")

                # 1) Voice verification
                if self.identity.has_voiceprint():
                    is_owner, v_sim = self.identity.verify_voice(audio, sample_rate=sr)
                    if is_owner:
                        msg = f"Voice verified (similarity={v_sim:.3f})"
                        self.logger.info(msg)
                        self._add_timeline("security", msg)
                    else:
                        warn = f"VOICE MISMATCH (similarity={v_sim:.3f})"
                        self.logger.warning(warn)
                        self._enter_security_stage("VOICE MISMATCH", speak=True)

                        if self.identity.has_faceprint():
                            face_ok = False
                            f_sim = 0.0

                            # pause camera monitor so only one thing uses webcam
                            try:
                                self.camera_monitor.stop()
                            except Exception as e:
                                self.logger.error(f"Failed to stop CameraMonitor before face verify: {e}")

                            try:
                                face_ok, f_sim = self.identity.verify_face_live(camera_index=0)
                            except Exception as e:
                                self.logger.error(f"Face verification crashed: {e}")
                                face_ok = False
                                f_sim = 0.0
                            finally:
                                # restart camera monitor
                                try:
                                    self.camera_monitor.start(camera_index=0)
                                except Exception as e:
                                    self.logger.error(f"Failed to restart CameraMonitor: {e}")

                            if face_ok:
                                ok_msg = f"Face verified (similarity={f_sim:.3f}). Proceeding."
                                self.logger.info(ok_msg)
                                self._add_timeline("security", ok_msg)
                            else:
                                bad = f"Face mismatch (similarity={f_sim:.3f}). Intruder alert."
                                self.logger.warning(bad)
                                self._intruder_alert()
                                return
                        else:
                            self.logger.warning("No faceprint enrolled. Intruder suspected.")
                            self._intruder_alert()
                            return
                else:
                    self.logger.info("No voiceprint enrolled; skipping voice verification.")

                # 2) If we reach here, identity is OK → do STT
                self.logger.info("Identity verified. Running STT...")
                text = self.stt_service.transcribe(audio, sample_rate=sr)
                text = text.strip()
                self.logger.info(f"STT result: '{text}'")
            except Exception as e:
                self.logger.error(f"Voice capture/STT failed: {e}")
                self._emit_system_message("I had trouble understanding your voice input.")
                self.window.set_status("IDLE")
                return
            finally:
                # Whatever happens, bring wake word back online
                try:
                    if hasattr(self, "wake_listener") and self.wake_listener is not None:
                        self.wake_listener.start()
                        self.logger.info("Wake listener restarted after command.")
                except Exception as e:
                    self.logger.error(f"Failed to restart wake listener: {e}")

            if not text:
                self._emit_system_message("I didn't catch anything from the microphone.")
                self.window.set_status("IDLE")
                return

            # Send recognized text back to Qt main thread
            self.voice_command_ready.emit(text)

    @QtCore.pyqtSlot(str)
    def _handle_voice_command_text(self, text: str):
        """
        Runs in Qt thread; we now have recognized text from voice.
        Treat it like a user command, but mark as [voice].
        """
        display_text = f"[voice] {text}"
        self.user_message.emit(display_text)
        self._add_timeline("voice", text)

        # Process the command
        self._process_command(text)

        # After command handling is done, we're ready again
        self.window.set_status("IDLE")
        ready_msg = "Ready for your next command."
        self._emit_system_message(ready_msg)
        self._add_timeline("system", ready_msg)

    # ---------- Command processing (shared) ----------

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

        elif parsed.type == CommandType.ENROLL_VOICE:
            self._start_voice_enrollment(parsed.message_to_user)

        elif parsed.type == CommandType.ENROLL_FACE:
            self._start_face_enrollment(parsed.message_to_user)

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

    # ---------- App launching / closing ----------

    def _handle_open_app(self, app_name: str, message: str):
        self._emit_system_message(message)
        self._add_timeline("action", f"Opening app: {app_name}")

        app_map = {
            "notepad": ["notepad.exe"],
            "chrome": ["chrome.exe"],
            "edge": ["msedge.exe"],
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
            "edge": ["msedge.exe"],
            "code": ["Code.exe", "code.exe"],
            "whatsapp": ["whatsapp.exe"],
        }

        targets = proc_map.get(app_name)
        if not targets:
            msg = "I don't know how to close that application yet."
            self._emit_system_message(msg)
            self._add_timeline("error", msg)
            return

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

    # ---------- Enrollment helpers ----------

    def _start_voice_enrollment(self, message: str):
        def worker():
            try:
                self._emit_system_message(message)
                self.window.set_status("ENROLL VOICE")
                self._add_timeline("enroll", "Voice enrollment started")
                self.identity.enroll_voice(samples=5, duration_sec=3.0)
                done = "Voice enrollment complete. Your voiceprint is now registered."
                self._emit_system_message(done)
                self._add_timeline("enroll", done)
            except Exception as e:
                err = f"Voice enrollment failed: {e}"
                self.logger.error(err)
                self._emit_system_message(err)
                self._add_timeline("error", err)
            finally:
                self.window.set_status("IDLE")

        threading.Thread(target=worker, daemon=True).start()

    def _start_face_enrollment(self, message: str):
        def worker():
            try:
                self._emit_system_message(message)
                self.window.set_status("ENROLL FACE")
                self._add_timeline("enroll", "Face enrollment started")
                self.identity.enroll_face(frames=10, camera_index=0)
                done = "Face enrollment complete. Your faceprint is now registered."
                self._emit_system_message(done)
                self._add_timeline("enroll", done)
            except Exception as e:
                err = f"Face enrollment failed: {e}"
                self.logger.error(err)
                self._emit_system_message(err)
                self._add_timeline("error", err)
            finally:
                self.window.set_status("IDLE")

        threading.Thread(target=worker, daemon=True).start()

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

    # ---------- Wake word handling ----------

    @QtCore.pyqtSlot()
    def _on_wake_word(self):
        """
        Called when Porcupine detects the wake word.
        """
        if self.camera_locked:
            self.logger.info("Wake word detected but camera is locked; ignoring.")
            return

        if self._recording_lock.locked():
            # Already handling a previous command
            self.logger.info("Wake word detected while already recording; ignoring.")
            return

        self.logger.info("Wake word accepted. Preparing for voice command.")
        self.window.set_status("AWAKE")
        msg = "Yes, I'm listening."
        # show in UI but DO NOT speak, to avoid recording our own voice
        self._emit_system_message(msg, speak=False)
        self._add_timeline("wake", "Wake word detected")

        # Start recording the command shortly after the wake word
        QtCore.QTimer.singleShot(200, self.start_voice_capture)


    # ---------- Camera security callbacks ----------

    def _camera_blocked(self):
        """
        Called when camera is covered (dark frames).
        """
        self.camera_locked = True
        self.window.set_theme(VortexTheme.SECURITY)
        self.window.set_status("CAMERA BLOCKED")

        msg = "Security warning: Camera feed obstructed or missing. Commands disabled."
        self._emit_system_message(msg)
        self._add_timeline("security", msg)

    def _camera_restored(self):
        """
        Called when camera feed becomes normal again.
        """
        self.camera_locked = False
        self.window.set_theme(VortexTheme.NORMAL)
        self.window.set_status("IDLE")

        msg = "Camera feed restored. Normal operations resumed."
        self._emit_system_message(msg)
        self._add_timeline("security", msg)

    # ---------- Security helpers ----------

    def _enter_security_stage(self, reason: str, speak: bool = True):
        self.window.set_theme(VortexTheme.SECURITY)
        self.window.set_status("SECURITY CHECK")
        msg = f"Security check: {reason}."
        if speak:
            self._emit_system_message(msg)
        else:
            self.system_message.emit(msg)
            self.logger.info(msg)
        self._add_timeline("security", msg)

    def _intruder_alert(self):
        self.window.set_theme(VortexTheme.SECURITY)
        self.window.set_status("LOCKDOWN")
        msg = "Intruder alert. Identity could not be verified. Command ignored."
        self._emit_system_message(msg)
        self._add_timeline("security", msg)

    # ---------- Utility ----------

    def _emit_system_message(self, text: str, speak: bool = True):
        """
        Send a system message to the UI and (optionally) speak it.
        """
        self.system_message.emit(text)
        if speak:
            self.tts.speak(text)
        self.logger.info(f"System message: {text}")


    def _add_timeline(self, kind: str, text: str):
        ev = self.timeline.add_event(kind, text)
        pretty = f"[{ev.timestamp.strftime('%H:%M:%S')}] ({kind}) {text}"
        self.timeline_entry.emit(pretty)

    def shutdown(self):
        self._friend_mode_running = False
        try:
            self.camera_monitor.stop()
        except Exception:
            pass
        try:
            if self.wake_listener is not None:
                self.wake_listener.stop()
        except Exception:
            pass
        self.tts.shutdown()
        self.logger.info("VORTEX shutting down.")

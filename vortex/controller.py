# vortex/controller.py

from __future__ import annotations

import subprocess
import threading
import random
import time
from typing import Optional, List
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
from .core.memory import MemoryManager, MemoryItem
from .core.camera_monitor import CameraMonitor
from .core.wake_word import WakeWordListener
from .core.workflow_engine import WorkflowEngine
from .core.personality import PersonalityProfile


class VortexController(QtCore.QObject):
    """
    Main orchestrator for VORTEX:
    - Connects UI, STT, TTS, security, workflows and personality.
    """

    # Signals into UI
    system_message = QtCore.pyqtSignal(str)
    user_message = QtCore.pyqtSignal(str)
    timeline_entry = QtCore.pyqtSignal(str)
    memory_snapshot = QtCore.pyqtSignal(str)

    # Voice pipeline
    voice_command_ready = QtCore.pyqtSignal(str)
    wake_word_detected = QtCore.pyqtSignal()

    # UI-change signals (to avoid touching widgets from worker threads)
    theme_change = QtCore.pyqtSignal(VortexTheme)
    status_change = QtCore.pyqtSignal(str)

    def __init__(self, window: VortexWindow, owner_name: str = "Varchasva"):
        super().__init__()
        self.window = window
        self.owner_name = owner_name

        # ---- Runtime state ----
        self.use_face_fallback: bool = False
        self._last_app_opened: Optional[str] = None
        self._last_memory_results: List[MemoryItem] = []
        self._recording_lock = threading.Lock()
        self._friend_mode_running: bool = True
        self._friend_thread: Optional[threading.Thread] = None
        self.camera_locked: bool = False

        # ---- Core components ----
        self.logger = setup_logging()
        self.command_engine = CommandEngine()
        self.tts = TTSService()
        self.timeline = TimelineManager()
        self.personality = PersonalityProfile(owner_name=owner_name)

        self.audio_manager = AudioManager()
        self.stt_service = STTService(
            model_size="tiny.en",
            device="cpu",
            compute_type="int8",
        )

        data_dir = Path(__file__).resolve().parents[1] / "data"
        self.identity = IdentityManager(
            audio_manager=self.audio_manager,
            logger=self.logger,
            data_dir=data_dir,
        )
        self.memory = MemoryManager(data_dir=data_dir, logger=self.logger)
        self.workflow_engine = WorkflowEngine(
            controller=self,
            data_dir=data_dir,
            logger=self.logger,
        )

        # Camera security monitor
        self.camera_monitor = CameraMonitor(
            identity_manager=self.identity,
            logger=self.logger,
            callback_on_blocked=self._camera_blocked,
            callback_on_restored=self._camera_restored,
        )

        # ---- Wire UI signals ----
        self.system_message.connect(self.window.append_system_message_animated)
        self.user_message.connect(self.window.append_user_command)
        self.timeline_entry.connect(self.window.add_timeline_entry)
        self.memory_snapshot.connect(self.window.update_memory_panel)

        # UI theme / status signals
        self.theme_change.connect(self.window.set_theme)
        self.status_change.connect(self.window.set_status)

        # UI -> controller inputs
        self.window.command_entered.connect(self.handle_user_command)
        self.window.voice_listen_requested.connect(self.start_voice_capture)

        # Voice pipeline events
        self.voice_command_ready.connect(self._handle_voice_command_text)
        self.wake_word_detected.connect(self._on_wake_word)

        # ---- Start background features ----
        self._start_friend_mode_thread()
        self.camera_monitor.start(camera_index=0)

        # ---- Initial greeting ----
        greet = self.personality.system_greeting()
        self._emit_system_message(greet)
        self.status_change.emit("IDLE")
        self._add_timeline("system", greet)
        self._refresh_memory_panel()

        # ---- Wake word (Porcupine) ----
        PORCUPINE_ACCESS_KEY = "h2cmEG5UAD2TDYKeQmxEXlbKGGa8wuElX6ZwBhZq3lOvF1XWvfKEJw=="  # replace with your real key
        self.wake_listener: Optional[WakeWordListener] = None

        if PORCUPINE_ACCESS_KEY:
            try:
                vortex_ppn = data_dir / "wakewords" / "vortex_en_windows_v3_0_0.ppn"
                if vortex_ppn.exists():
                    self.logger.info(f"Using custom Vortex wake word file: {vortex_ppn}")
                    self.wake_listener = WakeWordListener(
                        logger=self.logger,
                        on_detect=lambda: self.wake_word_detected.emit(),
                        access_key=PORCUPINE_ACCESS_KEY,
                        keyword_path=str(vortex_ppn),
                    )
                    wake_msg = 'Wake word online. Say "Vortex" to wake me.'
                else:
                    self.logger.warning(
                        f"Custom wakeword file not found at {vortex_ppn}. "
                        "Falling back to built-in 'jarvis'."
                    )
                    self.wake_listener = WakeWordListener(
                        logger=self.logger,
                        on_detect=lambda: self.wake_word_detected.emit(),
                        access_key=PORCUPINE_ACCESS_KEY,
                        keyword="jarvis",
                    )
                    wake_msg = 'Wake word online. Say "Jarvis" to wake me.'

                self.wake_listener.start()
                self.system_message.emit(wake_msg)
                self._add_timeline("wake", wake_msg)
            except Exception as e:
                self.logger.error(f"WakeWordListener init failed: {e}")
                self.system_message.emit("Wake word disabled (init error).")
                self._add_timeline("wake", "Wake word disabled (init error)")
        else:
            self.system_message.emit("Wake word disabled (no Porcupine access key).")
            self._add_timeline("wake", "Wake word disabled (no access key)")

    # -------------------------------------------------------------------------
    # TEXT COMMAND (keyboard)
    # -------------------------------------------------------------------------

    @QtCore.pyqtSlot(str)
    def handle_user_command(self, text: str):
        """Entry point for typed commands from the UI."""
        self.user_message.emit(text)
        self.logger.info(f"User command (typed): {text}")
        self._add_timeline("user", text)
        self._process_command(text)

    # -------------------------------------------------------------------------
    # VOICE CAPTURE + STT
    # -------------------------------------------------------------------------

    @QtCore.pyqtSlot()
    def start_voice_capture(self):
        """Trigger recording of a short phrase and STT."""
        if self._recording_lock.locked():
            self.logger.info("Voice capture requested but already recording; ignoring.")
            return

        self.logger.info("Voice capture requested by UI or wake word.")

        # Pause wake listener so it won't retrigger during recording
        try:
            if self.wake_listener is not None:
                self.wake_listener.stop()
        except Exception as e:
            self.logger.error(f"Failed to stop wake listener before recording: {e}")

        worker = threading.Thread(target=self._record_and_transcribe, daemon=True)
        worker.start()

    def _record_and_transcribe(self):
        with self._recording_lock:
            try:
                if self.camera_locked:
                    self._emit_system_message("Camera blocked. Ignoring command for security.")
                    return

                self.logger.info("Recording voice phrase...")
                audio, sr = self.audio_manager.record_phrase(duration_sec=3.0)
                self.logger.info("Recording finished, verifying identity...")

                # Voice verification (if enrolled)
                if self.identity.has_voiceprint():
                    is_owner, v_sim = self.identity.verify_voice(audio, sample_rate=sr)
                    if is_owner:
                        msg = f"Voice verified. similarity={v_sim:.3f}"
                        self.logger.info(msg)
                        self._add_timeline("security", msg)
                    else:
                        warn = f"VOICE MISMATCH. similarity={v_sim:.3f}"
                        self.logger.warning(warn)
                        self._enter_security_stage("VOICE MISMATCH", speak=True)
                        self._intruder_alert()
                        return
                else:
                    self.logger.info("No voiceprint enrolled; skipping voice verification.")

                # STT
                self.logger.info("Identity verified. Running STT...")
                text = self.stt_service.transcribe(audio, sample_rate=sr)
                text = text.strip()
                self.logger.info(f"STT result: '{text}'")

            except Exception as e:
                self.logger.error(f"Voice capture/STT failed: {e}")
                self._emit_system_message("I had trouble understanding your voice input.")
                self.status_change.emit("IDLE")
                return
            finally:
                # Restart wake listener after processing
                try:
                    if self.wake_listener is not None:
                        self.wake_listener.start()
                        self.logger.info("Wake listener restarted after voice command.")
                except Exception as e:
                    self.logger.error(f"Failed to restart wake listener: {e}")

            if not text:
                self._emit_system_message("I didn't catch anything from the microphone.")
                self.status_change.emit("IDLE")
                return

            # Deliver recognized text to the normal command path
            self.voice_command_ready.emit(text)

    @QtCore.pyqtSlot(str)
    def _handle_voice_command_text(self, text: str):
        """Handle voice-transcribed text as if the user typed it."""
        display_text = f"[voice] {text}"
        self.user_message.emit(display_text)
        self._add_timeline("voice", text)

        self._process_command(text)

        self.status_change.emit("IDLE")
        ready_msg = self.personality.ready_prompt()
        self._emit_system_message(ready_msg)
        self._add_timeline("system", ready_msg)

    # -------------------------------------------------------------------------
    # COMMAND PROCESSING
    # -------------------------------------------------------------------------

    def _process_command(self, text: str):
        lowered = text.strip().lower()

        # ------------------------------------------------------------------
        # High-priority natural commands (handled BEFORE CommandEngine)
        # ------------------------------------------------------------------

        # 1) Focus mode → run focus workflow
        if lowered in ("focus mode", "start focus mode", "enter focus mode"):
            ok = self.workflow_engine.run_workflow("focus_mode")
            if ok:
                msg = "Executing workflow 'focus mode'."
            else:
                msg = "I couldn't find any workflow called 'focus mode'."
            self._emit_system_message(msg, speak=False)
            self._add_timeline("workflow", msg)
            return

        # 2) OPEN NOTEPAD (force app command, avoid note-parser)
        if lowered in (
            "open notepad",
            "open note pad",
            "open the notepad",
            "notepad",
            "note pad",
        ):
            self._handle_open_app("notepad", "Opening notepad for you.", uses_context=False)
            return

        # 3) CLOSE NOTEPAD explicitly
        if lowered in (
            "close notepad",
            "close note pad",
            "close the notepad",
        ):
            self._handle_close_app("notepad", "Closing notepad for you.", uses_context=False)
            return

        # 4) CLOSE LAST APP (context: "close that", "close it")
        if lowered in (
            "close that",
            "close it",
            "close this",
        ):
            if self._last_app_opened:
                # Use last app context
                msg = f"Closing {self._last_app_opened} for you."
                self._handle_close_app(self._last_app_opened, msg, uses_context=True)
            else:
                msg = "I'm not sure what you want me to close."
                self._emit_system_message(msg)
                self._add_timeline("info", msg)
            return

        # 5) Forget / delete / remove last thing (for now, soft acknowledgement)
        if lowered in (
            "forget that",
            "forget it",
            "delete that note",
            "remove that note",
            "forget last note",
        ):
            msg = "Got it. I'll forget that."
            self._emit_system_message(msg)
            self._add_timeline("memory", msg)
            return

        # ------------------------------------------------------------------
        # Existing logic (wake word, workflows, parser, etc.)
        # ------------------------------------------------------------------

        # manual security reset
        if lowered in ("normal mode", "return to normal mode", "stand down"):
            self.theme_change.emit(VortexTheme.NORMAL)
            self.status_change.emit("IDLE")
            msg = "Returning to normal operational mode."
            self._emit_system_message(msg, speak=False)
            self._add_timeline("security", msg)
            return

        # Optional text-based "wake" trigger (purely cosmetic)
        if lowered in ("vortex", "hey vortex"):
            msg = "Yes, Varchasva. I'm listening."
            self._emit_system_message(msg)
            self._add_timeline("wake", "Text wake word used")
            return

        # workflow listing
        if lowered in ("list workflows", "show workflows", "what workflows do you have"):
            workflows = self.workflow_engine.list_workflows()
            if not workflows:
                msg = "You don't have any workflows defined yet."
            else:
                lines = [f"- {wf.name}: {wf.description}" for wf in workflows]
                msg = "Here are the workflows I know:\n" + "\n".join(lines)
            self._emit_system_message(msg, speak=False)
            self._add_timeline("workflow", msg)
            return

        # run workflow by name
        if lowered.startswith("run workflow"):
            name = lowered[len("run workflow") :].strip()
            if not name:
                msg = "Tell me which workflow to run, for example: run workflow focus mode."
                self._emit_system_message(msg, speak=False)
                self._add_timeline("workflow", msg)
                return

            ok = self.workflow_engine.run_workflow(name)
            if not ok:
                msg = f"I couldn't find any workflow called '{name}'."
                self._emit_system_message(msg, speak=False)
                self._add_timeline("workflow", msg)
            else:
                msg = f"Executing workflow '{name}'."
                self._emit_system_message(msg, speak=False)
                self._add_timeline("workflow", msg)
            return

        # --- regular commands via CommandEngine ---
        parsed = self.command_engine.parse(text)

        if parsed.type == CommandType.OPEN_APP and parsed.app_name:
            self._handle_open_app(parsed.app_name, parsed.message_to_user, uses_context=False)

        elif parsed.type == CommandType.CLOSE_APP and parsed.app_name:
            self._handle_close_app(parsed.app_name, parsed.message_to_user, uses_context=False)

        elif parsed.type == CommandType.NOTE_REMEMBER and parsed.note_text:
            self.memory.add(parsed.note_text, category="note")
            self.logger.info(f"Note stored: {parsed.note_text}")
            self._add_timeline("note", parsed.note_text)
            self._emit_system_message(parsed.message_to_user)
            self._refresh_memory_panel()

        elif parsed.type == CommandType.NOTE_QUERY:
            items = self.memory.list_recent(limit=5, category="note")
            self._last_memory_results = items[:]
            if not items:
                msg = "I don't have any notes stored yet."
            else:
                lines = [f"{i.id}) {i.text} ({i.timestamp})" for i in items]
                msg = "Here are your latest notes:\n" + "\n".join(lines)
            self._emit_system_message(msg)
            self._add_timeline("memory", msg)
            self._refresh_memory_panel()

        elif parsed.type == CommandType.SMALLTALK:
            reply = self.personality.chat_reply(parsed.raw_text)
            self._emit_system_message(reply)
            self._add_timeline("chat", f"You: {parsed.raw_text}\nVORTEX: {reply}")

        elif parsed.type == CommandType.UNKNOWN:
            reply = self.personality.chat_reply(parsed.raw_text)
            self._emit_system_message(reply)
            self._add_timeline("chat", f"You: {parsed.raw_text}\nVORTEX: {reply}")

    # -------------------------------------------------------------------------
    # APP CONTROL
    # -------------------------------------------------------------------------

    def _handle_open_app(self, app_name: str, message: str, uses_context: bool = False):
        resolved_app = app_name
        spoken_msg = message.replace("that", resolved_app)
        self._emit_system_message(spoken_msg)
        self._add_timeline("action", f"Opening app: {resolved_app}")

        # Map logical names to executable names / paths
        app_map = {
            "notepad": ["notepad.exe"],
            "chrome": ["chrome.exe"],
            "edge": ["msedge.exe"],
            "code": ["code.exe"],
            # Update this path for your machine if needed:
            "whatsapp": [r"whatsapp.exe"],
        }

        cmd = app_map.get(resolved_app)
        if not cmd:
            msg = "I don't know how to open that application yet."
            self._emit_system_message(msg)
            self._add_timeline("error", msg)
            return

        try:
            subprocess.Popen(cmd)
            self.logger.info(f"Opened application: {resolved_app} ({cmd})")
            self._last_app_opened = resolved_app
        except Exception as e:
            err = f"I tried to open {resolved_app} but something went wrong."
            self.logger.error(f"Failed to open {resolved_app}: {e}")
            self._emit_system_message(err)
            self._add_timeline("error", err)

    def _handle_close_app(self, app_name: str, message: str, uses_context: bool = False):
        resolved_app = app_name
        spoken_msg = (
            message.replace("it", resolved_app)
            .replace("that", resolved_app)
        )
        self._emit_system_message(spoken_msg)
        self._add_timeline("action", f"Closing app: {resolved_app}")

        proc_map = {
            "notepad": ["notepad.exe"],
            "chrome": ["chrome.exe"],
            "edge": ["chrome.exe", "msedge.exe"],
            "code": ["Code.exe", "code.exe"],
            "whatsapp": ["whatsapp.exe"],
        }

        targets = proc_map.get(resolved_app)
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
            self.logger.info(f"Closed application: {resolved_app}")
        else:
            msg = f"I couldn't find any running instance of {resolved_app}."
            self._emit_system_message(msg)
            self._add_timeline("info", msg)

    # -------------------------------------------------------------------------
    # FRIEND MODE (idle chatter)
    # -------------------------------------------------------------------------

    def _start_friend_mode_thread(self):
        def friend_loop():
            while self._friend_mode_running:
                delay = random.randint(60, 180)  # 1–3 minutes
                time.sleep(delay)
                msg = self.personality.idle_prompt()
                self._emit_system_message(msg)
                self._add_timeline("friend", msg)

        self._friend_thread = threading.Thread(target=friend_loop, daemon=True)
        self._friend_thread.start()

    # -------------------------------------------------------------------------
    # WAKE WORD HANDLER
    # -------------------------------------------------------------------------

    @QtCore.pyqtSlot()
    def _on_wake_word(self):
        if self.camera_locked:
            self.logger.info("Wake word detected but camera is locked; ignoring.")
            return

        if self._recording_lock.locked():
            self.logger.info("Wake word detected while already recording; ignoring.")
            return

        self.logger.info("Wake word accepted. Preparing for voice command.")
        self.status_change.emit("AWAKE")
        msg = "Yes, Varchasva. I'm listening."
        self._emit_system_message(msg, speak=False)
        self._add_timeline("wake", "Wake word detected (vortex)")

        # small delay before recording to avoid clipping
        QtCore.QTimer.singleShot(200, self.start_voice_capture)

    # -------------------------------------------------------------------------
    # CAMERA SECURITY
    # -------------------------------------------------------------------------

    def _camera_blocked(self):
        self.camera_locked = True
        self.theme_change.emit(VortexTheme.SECURITY)
        self.status_change.emit("CAMERA BLOCKED")
        msg = "Security warning: Camera feed obstructed or missing. Commands disabled."
        self._emit_system_message(msg)
        self._add_timeline("security", msg)

    def _camera_restored(self):
        self.camera_locked = False
        self.theme_change.emit(VortexTheme.NORMAL)
        self.status_change.emit("IDLE")
        msg = "Camera feed restored. Normal operations resumed."
        self._emit_system_message(msg)
        self._add_timeline("security", msg)

    # -------------------------------------------------------------------------
    # SECURITY HELPERS
    # -------------------------------------------------------------------------

    def _enter_security_stage(self, reason: str, speak: bool = True):
        self.theme_change.emit(VortexTheme.SECURITY)
        self.status_change.emit("SECURITY CHECK")
        msg = f"Security check: {reason}."
        if speak:
            self._emit_system_message(msg)
        else:
            self.system_message.emit(msg)
            self.logger.info(msg)
        self._add_timeline("security", msg)

    def _intruder_alert(self):
        self.theme_change.emit(VortexTheme.SECURITY)
        self.status_change.emit("LOCKDOWN")
        msg = "Intruder alert. Identity could not be verified. Command ignored."
        self._emit_system_message(msg)
        self._add_timeline("security", msg)

    # -------------------------------------------------------------------------
    # MEMORY PANEL
    # -------------------------------------------------------------------------

    def _refresh_memory_panel(self):
        items = self.memory.list_recent(limit=50)
        if not items:
            text = "No notes stored."
        else:
            lines = [f"{i.id}) [{i.category}] {i.text} ({i.timestamp})" for i in items]
            text = "\n".join(lines)
        self.memory_snapshot.emit(text)

    # -------------------------------------------------------------------------
    # UTILITY HELPERS
    # -------------------------------------------------------------------------

    def _emit_system_message(self, text: str, speak: bool = True):
        """
        Central helper for all VORTEX output.
        Pauses wake-word listener while speaking to avoid feedback.
        """
        self.system_message.emit(text)
        self.logger.info(f"System message: {text}")

        if speak:
            restarted = False
            try:
                if self.wake_listener is not None:
                    self.wake_listener.stop()
                    restarted = True
            except Exception as e:
                self.logger.error(f"Failed to pause wake listener before TTS: {e}")
                restarted = False

            try:
                self.tts.speak(text)
            finally:
                if restarted:
                    try:
                        if self.wake_listener is not None:
                            self.wake_listener.start()
                    except Exception as e:
                        self.logger.error(f"Failed to restart wake listener after TTS: {e}")

    def _add_timeline(self, kind: str, text: str):
        ev = self.timeline.add_event(kind, text)
        pretty = f"[{ev.timestamp.strftime('%H:%M:%S')}] ({kind}) {text}"
        self.timeline_entry.emit(pretty)

    # -------------------------------------------------------------------------
    # SHUTDOWN
    # -------------------------------------------------------------------------

    def shutdown(self):
        """Clean shutdown when the app is closing."""
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

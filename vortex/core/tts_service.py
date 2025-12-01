# vortex/core/tts_service.py

from __future__ import annotations

import threading
import queue
import subprocess
from typing import Optional


class TTSService:
    """
    TTS using Windows PowerShell + System.Speech.

    - 100% offline (uses built-in Windows voices)
    - One worker thread owns all TTS work
    - Each utterance uses a fresh PowerShell process, so there is
      no long-lived engine state that can get stuck.
    """

    def __init__(self, rate: int = 0, volume: int = 100, voice_name: Optional[str] = None):
        """
        rate: -10 .. 10 (0 = normal) – mapped inside PowerShell.
        volume: 0 .. 100
        voice_name: optional name of a specific installed voice (or None for default).
        """
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._running = True

        self._rate = rate
        self._volume = volume
        self._voice_name = voice_name

        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    # ---------- public API ----------

    def speak(self, text: str):
        """
        Queue text to be spoken. Non-blocking.
        """
        if not text or not self._running:
            return
        try:
            self._queue.put_nowait(text)
        except queue.Full:
            # avoid blocking everything if queue is somehow full
            pass

    def shutdown(self):
        """
        Stop worker thread.
        """
        self._running = False
        try:
            self._queue.put_nowait("")
        except Exception:
            pass
        try:
            if self._thread.is_alive():
                self._thread.join(timeout=2.0)
        except Exception:
            pass

    # ---------- internal ----------

    def _build_powershell_command(self) -> list[str]:
        """
        Build the PowerShell command that:
        - loads System.Speech
        - creates a SpeechSynthesizer
        - configures rate/volume/voice
        - reads text from stdin
        - speaks it
        """
        # Build the script as a single PowerShell command string
        script_parts = [
            "Add-Type -AssemblyName System.Speech;",
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;",
            f"$s.Rate = {int(self._rate)};",
            f"$s.Volume = {int(self._volume)};",
        ]

        if self._voice_name:
            # Try to select a specific voice by name (if present)
            script_parts.append(
                f"$voice = $s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Name -eq '{self._voice_name}' }};"
                "if ($voice) { $s.SelectVoice($voice.VoiceInfo.Name) }"
            )

        # Read full stdin as text and speak it
        script_parts.append("$text = [Console]::In.ReadToEnd();")
        script_parts.append("$s.Speak($text);")

        script = " ".join(script_parts)

        return ["powershell", "-NoLogo", "-NonInteractive", "-Command", script]

    def _worker_loop(self):
        ps_cmd = self._build_powershell_command()

        while self._running:
            try:
                text = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if not self._running:
                break
            if not text:
                continue

            try:
                # Start a new PowerShell process for each utterance, send text via stdin
                subprocess.run(
                    ps_cmd,
                    input=text,
                    text=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                # If TTS fails for some reason, log and continue
                print(f"[TTS ERROR] PowerShell TTS failed: {e}")
                continue

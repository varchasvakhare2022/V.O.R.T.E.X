from __future__ import annotations

import threading
import queue
from typing import Callable

import numpy as np
import sounddevice as sd
import pvporcupine


class WakeWordListener:
    def __init__(
        self,
        logger,
        on_detect: Callable[[], None],
        keyword: str,
        access_key: str,
    ):
        """
        on_detect: called whenever the wake word is detected.
        keyword: built-in Porcupine keyword, e.g. "jarvis"
        access_key: your Picovoice AccessKey (required).
        """
        self.logger = logger
        self.on_detect = on_detect
        self.keyword = keyword
        self.access_key = access_key

        self._porcupine = None
        self._audio_stream = None
        self._thread: threading.Thread | None = None
        self._running = False

        self._detect_queue: "queue.Queue[bool]" = queue.Queue()

    # ---------- lifecycle ----------

    def start(self):
        if self._running:
            return

        if not self.access_key:
            self.logger.error("WakeWordListener: access_key is empty. Wake word disabled.")
            return

        try:
            # List available built-in keywords in logs for debug
            try:
                kws = list(pvporcupine.KEYWORDS)
                self.logger.info(f"Porcupine built-in keywords: {kws}")
            except Exception:
                pass

            self._porcupine = pvporcupine.create(
                access_key=self.access_key,
                keywords=[self.keyword],
            )
            self.logger.info(
                f"WakeWordListener: initialized Porcupine with keyword '{self.keyword}'"
            )
        except Exception as e:
            self.logger.error(f"WakeWordListener: failed to init Porcupine: {e}")
            return

        try:
            self._audio_stream = sd.RawInputStream(
                samplerate=self._porcupine.sample_rate,
                blocksize=self._porcupine.frame_length,
                dtype="int16",
                channels=1,
                callback=self._audio_callback,
            )
            self._audio_stream.start()
        except Exception as e:
            self.logger.error(f"WakeWordListener: failed to open audio stream: {e}")
            if self._porcupine is not None:
                self._porcupine.delete()
                self._porcupine = None
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_detection_loop, daemon=True)
        self._thread.start()
        self.logger.info("WakeWordListener started and listening for wake word.")

    def stop(self):
        self._running = False
        try:
            if self._audio_stream is not None:
                self._audio_stream.stop()
                self._audio_stream.close()
        except Exception:
            pass

        if self._porcupine is not None:
            try:
                self._porcupine.delete()
            except Exception:
                pass
        self._porcupine = None
        self.logger.info("WakeWordListener stopped.")

    # ---------- internal ----------

    def _audio_callback(self, in_data, frame_count, time_info, status):
        if status:
            self.logger.warning(f"WakeWordListener audio status: {status}")
        if not self._porcupine:
            return

        pcm = np.frombuffer(in_data, dtype=np.int16)
        try:
            result = self._porcupine.process(pcm)
        except Exception as e:
            self.logger.error(f"WakeWordListener process error: {e}")
            return

        if result >= 0:
            # keyword detected
            try:
                self._detect_queue.put_nowait(True)
            except queue.Full:
                pass

    def _run_detection_loop(self):
        while self._running:
            try:
                _ = self._detect_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            self.logger.info("Wake word detected.")
            try:
                self.on_detect()
            except Exception as e:
                self.logger.error(f"WakeWordListener on_detect error: {e}")

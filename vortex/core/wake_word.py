# vortex/core/wake_word.py

from __future__ import annotations

import threading
from typing import Callable, Optional

import numpy as np
import pvporcupine
import sounddevice as sd


class WakeWordListener:
    """
    Simple Porcupine-based wake word listener.

    Supports two modes:
      - Built-in keyword: pass `keyword="jarvis"` etc.
      - Custom keyword file: pass `keyword_path="path/to/vortex.ppn"`

    Exactly one of (keyword, keyword_path) should be provided.
    """

    def __init__(
        self,
        logger,
        on_detect: Callable[[], None],
        access_key: str,
        keyword: Optional[str] = None,
        keyword_path: Optional[str] = None,
    ):
        self.logger = logger
        self.on_detect = on_detect
        self._running = False
        self._thread: Optional[threading.Thread] = None

        if not access_key:
            raise ValueError("Porcupine access_key is required for WakeWordListener")

        if keyword_path:
            self.logger.info(f"WakeWordListener: using custom keyword file: {keyword_path}")
            self._porcupine = pvporcupine.create(
                access_key=access_key,
                keyword_paths=[keyword_path],
            )
        else:
            if not keyword:
                keyword = "jarvis"
            builtins = pvporcupine.KEYWORDS
            self.logger.info(f"Porcupine built-in keywords: {builtins}")
            if keyword not in builtins:
                raise ValueError(
                    f"Keyword '{keyword}' is not a built-in Porcupine keyword. "
                    f"Available: {', '.join(builtins)}"
                )

            self.logger.info(f"WakeWordListener: using built-in keyword: {keyword}")
            self._porcupine = pvporcupine.create(
                access_key=access_key,
                keywords=[keyword],
            )

        self.sample_rate = self._porcupine.sample_rate
        self.frame_length = self._porcupine.frame_length

    # -------------- public API --------------

    def start(self):
        """Start the wake word listening loop in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.logger.info("WakeWordListener: started.")

    def stop(self):
        """Stop listening and join the background thread."""
        if not self._running:
            return
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.logger.info("WakeWordListener: stopped.")

    # -------------- internal loop --------------

    def _run(self):
        try:
            with sd.InputStream(
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.frame_length,
                dtype="int16",
            ) as stream:
                self.logger.info(
                    f"WakeWordListener: audio stream opened "
                    f"(sample_rate={self.sample_rate}, frame_length={self.frame_length})"
                )

                while self._running:
                    audio_frame, _ = stream.read(self.frame_length)
                    pcm = np.frombuffer(audio_frame, dtype=np.int16)

                    keyword_index = self._porcupine.process(pcm)
                    if keyword_index >= 0:
                        self.logger.info("WakeWordListener: wake word detected.")
                        try:
                            self.on_detect()
                        except Exception as cb_err:
                            self.logger.error(f"WakeWordListener: callback error: {cb_err}")
        except Exception as e:
            self.logger.error(f"WakeWordListener: error in loop: {e}")
        finally:
            self.logger.info("WakeWordListener: exiting audio loop.")

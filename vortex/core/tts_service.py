# vortex/core/tts_service.py

"""
TTSService: simple non-blocking text-to-speech using pyttsx3.

Phase 1:
- Single voice
- Sequential speech
- Runs in a background thread so the UI doesn't freeze
"""

import threading
from queue import Queue, Empty
import pyttsx3
import time


class TTSService:
    def __init__(self):
        self._engine = pyttsx3.init()
        # You can tweak voice, rate, volume here
        self._engine.setProperty("rate", 175)
        self._engine.setProperty("volume", 1.0)

        self._queue: "Queue[str]" = Queue()
        self._running = True

        # Dedicated thread that consumes text from the queue and speaks it
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _worker(self):
        while self._running:
            try:
                text = self._queue.get(timeout=0.2)
            except Empty:
                continue
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as e:
                # In Phase 1 we just print. Later we'll integrate proper logging.
                print(f"[TTSService] Error during speak: {e}")

    def speak(self, text: str):
        """
        Public method to request speech.
        Adds text to the queue to avoid blocking caller.
        """
        if not text:
            return
        self._queue.put(text)

    def shutdown(self):
        """
        Cleanly stop the background thread and pyttsx3 engine.
        """
        self._running = False
        # Drain queue quickly
        try:
            while True:
                self._queue.get_nowait()
        except Empty:
            pass
        # Give the worker time to exit
        time.sleep(0.3)
        try:
            self._engine.stop()
        except Exception:
            pass

# vortex/core/audio_manager.py

"""
AudioManager: handles microphone recording for short voice commands.

Phase 2A:
- Simple "push to talk" recording
- Called from a background thread so the GUI never blocks
"""

from __future__ import annotations

import sounddevice as sd
import numpy as np


class AudioManager:
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels

    def record_phrase(self, duration_sec: float = 4.0) -> tuple[np.ndarray, int]:
        """
        Record a short audio phrase from the default microphone.

        Returns:
            (audio_samples, sample_rate)
            audio_samples is a 1D float32 numpy array in range [-1, 1]
        """
        frames = int(duration_sec * self.sample_rate)
        recording = sd.rec(
            frames,
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
        )
        sd.wait()  # blocking until recording is done
        # Flatten to mono 1D array
        audio = recording.reshape(-1)
        return audio, self.sample_rate

# vortex/core/stt_service.py

"""
STTService: offline speech-to-text using faster-whisper (Whisper tiny model).

Phase 2A:
- Transcribe short voice commands
- Optimized for speed, not perfect accuracy
"""

from __future__ import annotations

from faster_whisper import WhisperModel
import numpy as np
from typing import Tuple


class STTService:
    def __init__(
        self,
        model_size: str = "tiny",
        device: str = "cuda",
        compute_type: str = "float16",
    ):
        """
        model_size: "tiny", "base", etc.
        device: "cpu" or "cuda" if you have GPU
        compute_type: "int8" for speed on CPU
        """
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        """
        Transcribe a mono audio array (float32) with given sample_rate.
        Returns the recognized text (lowercased, stripped).
        """
        if audio.ndim != 1:
            audio = audio.reshape(-1)

        # faster-whisper accepts numpy float32
        segments, _ = self.model.transcribe(
            audio,
            language="en",        # adjust later if you want multi-language
            beam_size=1,
            best_of=1,
        )

        text = "".join(segment.text for segment in segments).strip()
        return text

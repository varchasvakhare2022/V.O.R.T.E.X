# vortex/core/stt_service.py

from __future__ import annotations

from faster_whisper import WhisperModel
import numpy as np
from typing import Tuple


class STTService:
    def __init__(
        self,
        model_size: str = "tiny.en",   # use English-only tiny for speed & accuracy
        device: str = "cpu",
        compute_type: str = "int8",    # good for CPU
    ):
        """
        model_size: "tiny.en", "base.en", etc.
        device: "cpu" or "cuda"
        compute_type: "int8" for CPU, "float16" for GPU
        """
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        """
        Transcribe a mono audio array (float32) with given sample_rate.
        Returns the recognized text (lowercased, stripped).
        """
        if audio.ndim != 1:
            audio = audio.reshape(-1)

        segments, _ = self.model.transcribe(
            audio,
            language="en",
            beam_size=1,
            best_of=1,
            condition_on_previous_text=False,
            temperature=0,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
        )

        text = "".join(segment.text for segment in segments).strip()
        return text

# vortex/core/identity.py

"""
IdentityManager for VORTEX.

- Handles voice enrollment & verification (owner vs intruder)
- Handles face enrollment & verification using InsightFace
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple
import threading

import numpy as np
import cv2

from resemblyzer import VoiceEncoder
from numpy.linalg import norm
import insightface


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (norm(a) * norm(b) + 1e-9))


class IdentityManager:
    """
    Manages biometric identity:
    - Voiceprint using resemblyzer
    - Face embedding using InsightFace

    All files are stored in data_dir:
      - voiceprint.npy
      - faceprint.npy
    """

    def __init__(self, audio_manager, logger, data_dir: Path | None = None):
        self.audio_manager = audio_manager
        self.logger = logger

        if data_dir is None:
            # project_root / data
            self.data_dir = Path(__file__).resolve().parents[2] / "data"
        else:
            self.data_dir = Path(data_dir)

        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.voice_file = self.data_dir / "voiceprint.npy"
        self.face_file = self.data_dir / "faceprint.npy"

        self.voice_encoder: Optional[VoiceEncoder] = None
        self.face_app = None  # InsightFace app

        # thresholds: tweak as you test
        self.voice_threshold = 0.75
        self.face_threshold = 0.8  # cosine similarity for L2-normalized embeddings

        # lazy init locks
        self._voice_lock = threading.Lock()
        self._face_lock = threading.Lock()

    # ---------- lazy model loading ----------

    def _ensure_voice_encoder(self):
        with self._voice_lock:
            if self.voice_encoder is None:
                self.logger.info("Loading voice encoder (resemblyzer)...")
                self.voice_encoder = VoiceEncoder()
                self.logger.info("Voice encoder loaded.")

    def _ensure_face_app(self):
        with self._face_lock:
            if self.face_app is None:
                self.logger.info("Loading InsightFace model...")
                app = insightface.app.FaceAnalysis(
                    name="buffalo_l", providers=["CPUExecutionProvider"]
                )
                app.prepare(ctx_id=0, det_size=(640, 640))
                self.face_app = app
                self.logger.info("InsightFace model loaded.")

    # ---------- VOICE ENROLLMENT & VERIFY ----------

    def enroll_voice(self, samples: int = 5, duration_sec: float = 3.0):
        """
        Interactively record N samples and build an average voiceprint.
        """
        self._ensure_voice_encoder()
        enc = self.voice_encoder

        embeddings = []
        for i in range(samples):
            self.logger.info(f"Voice enrollment: recording sample {i + 1}/{samples}")
            audio, sr = self.audio_manager.record_phrase(duration_sec=duration_sec)
            # resemblyzer expects 16k mono float32 in [-1, 1] → we already have that
            emb = enc.embed_utterance(audio)
            embeddings.append(emb)

        if not embeddings:
            raise RuntimeError("No voice embeddings collected.")

        mean_emb = np.mean(np.stack(embeddings, axis=0), axis=0)
        np.save(self.voice_file, mean_emb)
        self.logger.info(f"Voiceprint saved to {self.voice_file}")

    def has_voiceprint(self) -> bool:
        return self.voice_file.exists()

    def verify_voice(
        self, audio: np.ndarray, sample_rate: int
    ) -> Tuple[bool, float]:
        """
        Compare incoming audio with stored voiceprint.
        Returns (is_owner, similarity_score).
        """
        if not self.voice_file.exists():
            self.logger.warning("No voiceprint enrolled yet.")
            return False, 0.0

        self._ensure_voice_encoder()
        enc = self.voice_encoder

        stored = np.load(self.voice_file)
        probe = enc.embed_utterance(audio)

        sim = cosine_sim(stored, probe)
        self.logger.info(f"Voice similarity: {sim:.3f}")
        return sim >= self.voice_threshold, sim

    # ---------- FACE ENROLLMENT & VERIFY ----------

    def enroll_face(self, frames: int = 10, camera_index: int = 0):
        """
        Capture multiple frames from webcam, collect face embeddings, and average.
        """
        self._ensure_face_app()
        app = self.face_app

        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            raise RuntimeError("Could not open webcam for face enrollment.")

        embeddings = []
        try:
            collected = 0
            while collected < frames:
                ret, frame = cap.read()
                if not ret:
                    continue
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                faces = app.get(rgb)
                if not faces:
                    continue
                # take the largest face
                face = max(faces, key=lambda f: f.bbox[2] * f.bbox[3])
                emb = face.embedding.astype(np.float32)
                # normalize
                emb = emb / (norm(emb) + 1e-9)
                embeddings.append(emb)
                collected += 1
                self.logger.info(f"Face enrollment: collected {collected}/{frames}")
        finally:
            cap.release()

        if not embeddings:
            raise RuntimeError("No face embeddings collected.")

        mean_emb = np.mean(np.stack(embeddings, axis=0), axis=0)
        # normalize again
        mean_emb = mean_emb / (norm(mean_emb) + 1e-9)
        np.save(self.face_file, mean_emb)
        self.logger.info(f"Faceprint saved to {self.face_file}")

    def has_faceprint(self) -> bool:
        return self.face_file.exists()

    def verify_face_live(
        self, camera_index: int = 0, max_attempts: int = 10
    ) -> Tuple[bool, float]:
        """
        Capture a few frames and check if any face matches stored faceprint.
        """
        if not self.face_file.exists():
            self.logger.warning("No faceprint enrolled yet.")
            return False, 0.0

        self._ensure_face_app()
        app = self.face_app

        stored = np.load(self.face_file).astype(np.float32)
        stored = stored / (norm(stored) + 1e-9)

        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            self.logger.error("Could not open webcam for face verification.")
            return False, 0.0

        best_sim = -1.0
        ok = False
        try:
            for _ in range(max_attempts):
                ret, frame = cap.read()
                if not ret:
                    continue
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                faces = app.get(rgb)
                if not faces:
                    continue
                face = max(faces, key=lambda f: f.bbox[2] * f.bbox[3])
                emb = face.embedding.astype(np.float32)
                emb = emb / (norm(emb) + 1e-9)
                sim = cosine_sim(stored, emb)
                best_sim = max(best_sim, sim)
                self.logger.info(f"Face similarity attempt: {sim:.3f}")
                if sim >= self.face_threshold:
                    ok = True
                    break
        finally:
            cap.release()

        return ok, best_sim

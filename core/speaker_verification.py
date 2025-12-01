"""
Speaker Verification Service.
Verifies that voice commands come from the authorized owner.
Uses voice embedding comparison to detect unauthorized speakers.
"""

import logging
import numpy as np
from typing import List, Optional
import os
import pickle


class SpeakerVerifier:
    """
    Speaker verification service.
    Enrolls owner's voice and verifies if incoming audio matches the owner.
    """
    
    # Audio configuration (must match AudioManager)
    SAMPLE_RATE = 16000  # 16kHz
    CHUNK_DURATION = 0.5  # Process audio in 0.5 second chunks for feature extraction
    
    def __init__(self, voice_profile_path: str = "data/voice_profile/", test_mode: bool = True):
        """
        Initialize speaker verifier.
        
        Args:
            voice_profile_path: Directory path to store voice profile data
            test_mode: If True, always returns True for testing (bypasses verification)
        """
        self.logger = logging.getLogger("VORTEX.SpeakerVerifier")
        self.voice_profile_path = voice_profile_path
        self.owner_embeddings: List[np.ndarray] = []
        self.is_enrolled = False
        self.similarity_threshold = 0.7  # Threshold for matching (0.0 to 1.0)
        self.test_mode = test_mode  # For testing: always return True
        
        # Create voice profile directory if it doesn't exist
        os.makedirs(self.voice_profile_path, exist_ok=True)
        
        # Try to load existing voice profile
        if not self.test_mode:
            self._load_voice_profile()
        else:
            self.logger.info("Speaker verification in TEST MODE - all speakers will be accepted")
    
    def enroll_owner(self, samples: List[bytes]) -> None:
        """
        Enroll the owner's voice using multiple audio samples.
        Should be called during initial setup with several samples of the owner speaking.
        
        Args:
            samples: List of audio byte samples (raw audio data)
        """
        if not samples:
            self.logger.warning("No samples provided for enrollment")
            return
        
        self.logger.info(f"Enrolling owner voice with {len(samples)} samples")
        embeddings = []
        
        for i, sample in enumerate(samples):
            try:
                embedding = self._extract_features(sample)
                if embedding is not None:
                    embeddings.append(embedding)
                    self.logger.debug(f"Extracted features from sample {i+1}/{len(samples)}")
            except Exception as e:
                self.logger.error(f"Error processing enrollment sample {i+1}: {e}", exc_info=True)
        
        if embeddings:
            self.owner_embeddings = embeddings
            self.is_enrolled = True
            self._save_voice_profile()
            self.logger.info(f"Owner voice enrolled successfully with {len(embeddings)} embeddings")
        else:
            self.logger.error("Failed to extract features from any enrollment samples")
            self.is_enrolled = False
    
    def verify_speaker(self, sample: bytes) -> bool:
        """
        Verify if the audio sample matches the enrolled owner's voice.
        
        Args:
            sample: Raw audio bytes to verify
            
        Returns:
            True if the speaker matches the owner, False otherwise
        """
        # TEST MODE: Always return True for testing
        if self.test_mode:
            self.logger.debug("TEST MODE: Accepting speaker (bypassing verification)")
            return True
        
        if not self.is_enrolled:
            self.logger.warning("No owner voice enrolled, cannot verify speaker")
            return False
        
        if not sample or len(sample) == 0:
            self.logger.warning("Empty audio sample provided for verification")
            return False
        
        try:
            # Extract features from the sample
            sample_embedding = self._extract_features(sample)
            if sample_embedding is None:
                self.logger.warning("Failed to extract features from audio sample")
                return False
            
            # Compare against all enrolled embeddings
            similarities = []
            for owner_embedding in self.owner_embeddings:
                similarity = self._cosine_similarity(sample_embedding, owner_embedding)
                similarities.append(similarity)
            
            # Use maximum similarity (best match)
            max_similarity = max(similarities) if similarities else 0.0
            avg_similarity = np.mean(similarities) if similarities else 0.0
            
            self.logger.debug(f"Speaker verification: max_similarity={max_similarity:.3f}, "
                           f"avg_similarity={avg_similarity:.3f}, threshold={self.similarity_threshold}")
            
            # Check if similarity meets threshold
            is_owner = max_similarity >= self.similarity_threshold
            
            if is_owner:
                self.logger.info(f"Speaker verified as owner (similarity: {max_similarity:.3f})")
            else:
                self.logger.warning(f"Speaker NOT verified - possible intruder! "
                                 f"(similarity: {max_similarity:.3f} < {self.similarity_threshold})")
            
            return is_owner
        
        except Exception as e:
            self.logger.error(f"Error during speaker verification: {e}", exc_info=True)
            return False
    
    def _extract_features(self, audio_bytes: bytes) -> Optional[np.ndarray]:
        """
        Extract feature vector (embedding) from audio bytes.
        
        TODO: Replace with real voice embedding model:
        - Use resemblyzer library (simple, good quality)
          from resemblyzer import VoiceEncoder
          encoder = VoiceEncoder()
          embedding = encoder.embed_utterance(audio_array)
        
        - Use pyannote.audio (more advanced, speaker diarization)
          from pyannote.audio import Inference
          model = Inference("speechbrain/spkrec-ecapa-voxceleb")
          embedding = model({"waveform": audio_tensor, "sample_rate": 16000})
        
        - Use speechbrain (speaker recognition)
          from speechbrain.inference.speaker import EncoderClassifier
          classifier = EncoderClassifier.from_hparams(...)
          embedding = classifier.encode_batch(audio_tensor)
        
        - Use custom MFCC + statistical features (simpler, less accurate)
          Extract MFCC coefficients and compute statistics (mean, std, etc.)
        
        For now, this is a placeholder that uses simple statistical features.
        
        Args:
            audio_bytes: Raw audio data
            
        Returns:
            Feature vector (numpy array) or None on error
        """
        try:
            # Convert bytes to numpy array
            # Audio is 16-bit integers (2 bytes per sample)
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            
            # Normalize to float32 range [-1.0, 1.0]
            audio_float = audio_array.astype(np.float32) / 32768.0
            
            # PLACEHOLDER: Simple feature extraction
            # TODO: Replace with real embedding model
            
            # Extract basic statistical features as placeholder
            features = []
            
            # Energy features
            features.append(np.mean(np.abs(audio_float)))
            features.append(np.std(audio_float))
            features.append(np.max(np.abs(audio_float)))
            
            # Spectral features (simple FFT-based)
            fft = np.fft.rfft(audio_float)
            magnitude = np.abs(fft)
            
            # Spectral centroid
            freqs = np.fft.rfftfreq(len(audio_float), 1.0 / self.SAMPLE_RATE)
            if np.sum(magnitude) > 0:
                spectral_centroid = np.sum(freqs * magnitude) / np.sum(magnitude)
            else:
                spectral_centroid = 0.0
            features.append(spectral_centroid)
            
            # Spectral rolloff (frequency below which 85% of energy is contained)
            cumsum_magnitude = np.cumsum(magnitude)
            total_energy = cumsum_magnitude[-1]
            if total_energy > 0:
                rolloff_idx = np.where(cumsum_magnitude >= 0.85 * total_energy)[0]
                spectral_rolloff = freqs[rolloff_idx[0]] if len(rolloff_idx) > 0 else 0.0
            else:
                spectral_rolloff = 0.0
            features.append(spectral_rolloff)
            
            # Zero crossing rate
            zero_crossings = np.sum(np.diff(np.signbit(audio_float)))
            zcr = zero_crossings / len(audio_float)
            features.append(zcr)
            
            # Additional statistical moments
            features.append(np.median(np.abs(audio_float)))
            features.append(np.percentile(np.abs(audio_float), 75))
            features.append(np.percentile(np.abs(audio_float), 25))
            
            # Convert to numpy array and normalize
            feature_vector = np.array(features, dtype=np.float32)
            
            # Normalize to unit vector for cosine similarity
            norm = np.linalg.norm(feature_vector)
            if norm > 0:
                feature_vector = feature_vector / norm
            
            return feature_vector
        
        except Exception as e:
            self.logger.error(f"Error extracting features: {e}", exc_info=True)
            return None
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Compute cosine similarity between two feature vectors.
        
        Args:
            vec1: First feature vector
            vec2: Second feature vector
            
        Returns:
            Cosine similarity value between -1.0 and 1.0 (typically 0.0 to 1.0 for normalized vectors)
        """
        try:
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
        
        except Exception as e:
            self.logger.error(f"Error computing cosine similarity: {e}", exc_info=True)
            return 0.0
    
    def _save_voice_profile(self):
        """Save enrolled voice profile to disk."""
        try:
            profile_file = os.path.join(self.voice_profile_path, "owner_voice.pkl")
            
            profile_data = {
                'embeddings': self.owner_embeddings,
                'is_enrolled': self.is_enrolled,
                'similarity_threshold': self.similarity_threshold
            }
            
            with open(profile_file, 'wb') as f:
                pickle.dump(profile_data, f)
            
            self.logger.info(f"Voice profile saved to {profile_file}")
        
        except Exception as e:
            self.logger.error(f"Error saving voice profile: {e}", exc_info=True)
    
    def _load_voice_profile(self):
        """Load enrolled voice profile from disk."""
        try:
            profile_file = os.path.join(self.voice_profile_path, "owner_voice.pkl")
            
            if not os.path.exists(profile_file):
                self.logger.info("No existing voice profile found")
                return
            
            with open(profile_file, 'rb') as f:
                profile_data = pickle.load(f)
            
            self.owner_embeddings = profile_data.get('embeddings', [])
            self.is_enrolled = profile_data.get('is_enrolled', False)
            self.similarity_threshold = profile_data.get('similarity_threshold', 0.7)
            
            if self.is_enrolled and self.owner_embeddings:
                self.logger.info(f"Voice profile loaded: {len(self.owner_embeddings)} embeddings")
            else:
                self.logger.warning("Voice profile file exists but appears invalid")
                self.is_enrolled = False
        
        except Exception as e:
            self.logger.error(f"Error loading voice profile: {e}", exc_info=True)
            self.is_enrolled = False
    
    def set_similarity_threshold(self, threshold: float):
        """
        Set the similarity threshold for verification.
        Higher values = stricter matching (fewer false positives, more false negatives)
        Lower values = more lenient matching (more false positives, fewer false negatives)
        
        Args:
            threshold: Similarity threshold between 0.0 and 1.0
        """
        if 0.0 <= threshold <= 1.0:
            self.similarity_threshold = threshold
            self.logger.info(f"Similarity threshold set to {threshold}")
            self._save_voice_profile()
        else:
            self.logger.warning(f"Invalid threshold {threshold}, must be between 0.0 and 1.0")
    
    def clear_enrollment(self):
        """Clear the enrolled voice profile."""
        self.owner_embeddings = []
        self.is_enrolled = False
        
        # Delete profile file
        try:
            profile_file = os.path.join(self.voice_profile_path, "owner_voice.pkl")
            if os.path.exists(profile_file):
                os.remove(profile_file)
                self.logger.info("Voice profile cleared")
        except Exception as e:
            self.logger.error(f"Error clearing voice profile: {e}", exc_info=True)


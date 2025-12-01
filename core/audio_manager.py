"""
Audio Manager module.
Orchestrates continuous audio capture, wake-word detection, and command recording.
Runs in background thread to avoid blocking the GUI.
"""

import pyaudio
import threading
import queue
import time
import numpy as np
from typing import Callable, Optional
from collections import deque


class AudioManager:
    """
    Manages continuous audio capture with wake-word detection and command recording.
    Runs in a background thread to keep the GUI responsive.
    """
    
    # Audio configuration constants
    CHUNK_SIZE = 1024  # Audio frames per buffer
    SAMPLE_RATE = 16000  # 16kHz sample rate (good for speech)
    CHANNELS = 1  # Mono audio
    FORMAT = pyaudio.paInt16  # 16-bit integer format
    
    # Command recording duration (seconds)
    COMMAND_RECORDING_DURATION = 5
    
    def __init__(self, energy_threshold: Optional[float] = None):
        """
        Initialize AudioManager with PyAudio.
        
        Args:
            energy_threshold: Custom energy threshold for wake-word detection.
                            If None, uses default (500.0). Lower = more sensitive.
        """
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.is_listening = False
        self.is_recording_command = False
        self.audio_thread = None
        self.audio_queue = queue.Queue()
        
        # Callbacks
        self.wake_word_callback: Optional[Callable] = None
        self.command_audio_callback: Optional[Callable[[bytes], None]] = None
        self.energy_callback: Optional[Callable[[float], None]] = None  # For UI visualization
        
        # Wake-word detection placeholder
        self.wake_word_detector = None  # Will be set when real detector is integrated
        
        # Simple energy-based wake-word detection
        self.energy_threshold = energy_threshold if energy_threshold is not None else 500.0
        self.energy_history = deque(maxlen=20)  # Keep last 20 energy values for better smoothing
        self.last_wake_word_time = 0
        self.wake_word_cooldown = 3.0  # Minimum seconds between wake word triggers (increased)
        self.debug_mode = False  # Set to True to see energy values in logs
        
        # Improved detection: require sustained speech
        self.speech_start_time = None
        self.min_speech_duration = 0.3  # Minimum 0.3 seconds of speech to trigger
        self.quiet_threshold = 50.0  # Energy below this is considered silence
        self.quiet_duration_before_speech = 0.2  # Need 0.2s of quiet before speech
        self.quiet_history = deque(maxlen=10)  # Track quiet periods
        
        # Lock for thread-safe operations
        self.lock = threading.Lock()
    
    def start_listening(self):
        """
        Start continuous audio capture in a background thread.
        Begins in wake-word listening mode.
        """
        if self.is_listening:
            return
        
        with self.lock:
            self.is_listening = True
            self.is_recording_command = False
        
        # Open audio stream
        try:
            self.stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.SAMPLE_RATE,
                input=True,
                frames_per_buffer=self.CHUNK_SIZE,
                stream_callback=self._audio_callback
            )
            self.stream.start_stream()
        except Exception as e:
            print(f"Error opening audio stream: {e}")
            self.is_listening = False
            return
        
        # Start background thread for processing audio
        self.audio_thread = threading.Thread(target=self._audio_processing_loop, daemon=True)
        self.audio_thread.start()
    
    def stop_listening(self):
        """Stop audio capture and clean up resources."""
        with self.lock:
            self.is_listening = False
            self.is_recording_command = False
        
        # Stop and close audio stream
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                print(f"Error closing audio stream: {e}")
            self.stream = None
        
        # Wait for thread to finish
        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=1.0)
        
        self.audio_queue.put(None)  # Signal thread to exit
    
    def set_wake_word_callback(self, callback: Callable):
        """
        Set callback function to be called when wake word is detected.
        
        Args:
            callback: Function to call when "Vortex" is detected (no arguments)
        """
        self.wake_word_callback = callback
    
    def set_command_audio_callback(self, callback: Callable[[bytes], None]):
        """
        Set callback function to receive recorded command audio.
        
        Args:
            callback: Function that receives audio data (bytes) as argument
        """
        self.command_audio_callback = callback
    
    def set_energy_callback(self, callback: Callable[[float], None]):
        """
        Set callback function to receive real-time audio energy levels.
        Used for UI visualization.
        
        Args:
            callback: Function that receives energy (float) as argument
        """
        self.energy_callback = callback
    
    def _calculate_energy(self, audio_chunk: bytes) -> Optional[float]:
        """
        Calculate audio energy from chunk.
        
        Args:
            audio_chunk: Raw audio bytes
            
        Returns:
            Energy value or None if invalid
        """
        try:
            if not audio_chunk or len(audio_chunk) == 0:
                return None
            
            audio_array = np.frombuffer(audio_chunk, dtype=np.int16)
            if len(audio_array) == 0:
                return None
            
            squared = audio_array.astype(np.float64) ** 2
            mean_squared = np.mean(squared)
            
            if mean_squared <= 0 or np.isnan(mean_squared) or np.isinf(mean_squared):
                return 0.0
            
            energy = np.sqrt(mean_squared)
            if np.isnan(energy) or np.isinf(energy):
                return 0.0
            
            return float(energy)
        
        except Exception:
            return None
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """
        PyAudio stream callback - called for each audio chunk.
        This runs in a separate thread managed by PyAudio.
        """
        if status:
            print(f"Audio stream status: {status}")
        
        # Put audio data in queue for processing
        if self.is_listening:
            self.audio_queue.put(in_data)
        
        return (None, pyaudio.paContinue)
    
    def _audio_processing_loop(self):
        """
        Background thread loop that processes audio chunks.
        Handles wake-word detection and command recording.
        """
        command_audio_buffer = []
        command_start_time = None
        
        while self.is_listening:
            try:
                # Get audio chunk from queue (with timeout to allow checking is_listening)
                try:
                    audio_chunk = self.audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                if audio_chunk is None:  # Exit signal
                    break
                
                with self.lock:
                    recording_command = self.is_recording_command
                
                if recording_command:
                    # Command capture mode: collect audio for STT and speaker verification
                    command_audio_buffer.append(audio_chunk)
                    
                    if command_start_time is None:
                        command_start_time = time.time()
                    
                    # Check if we've recorded enough audio
                    elapsed = time.time() - command_start_time
                    if elapsed >= self.COMMAND_RECORDING_DURATION:
                        # Send complete command audio to callback
                        if self.command_audio_callback:
                            complete_audio = b''.join(command_audio_buffer)
                            self.command_audio_callback(complete_audio)
                        
                        # Reset for next wake-word detection
                        command_audio_buffer = []
                        command_start_time = None
                        with self.lock:
                            self.is_recording_command = False
                
                else:
                    # Calculate energy for visualization
                    energy = self._calculate_energy(audio_chunk)
                    if energy is not None and self.energy_callback:
                        try:
                            self.energy_callback(energy)
                        except Exception:
                            pass
                    
                    # Wake-word listening mode: check for "Vortex"
                    wake_word_detected = self._detect_wake_word(audio_chunk)
                    
                    if wake_word_detected:
                        # Switch to command capture mode
                        with self.lock:
                            self.is_recording_command = True
                        
                        command_audio_buffer = []
                        command_start_time = time.time()
                        
                        # Notify via callback
                        if self.wake_word_callback:
                            self.wake_word_callback()
            
            except Exception as e:
                print(f"Error in audio processing loop: {e}")
                continue
    
    def _detect_wake_word(self, audio_chunk: bytes) -> bool:
        """
        Improved energy-based wake-word detection with noise filtering.
        
        This is a temporary implementation that detects sustained speech activity.
        For production, replace with real wake-word detection:
        - Integrate Porcupine (Picovoice) for production wake-word detection
        - Or use a custom trained model (e.g., with TensorFlow/PyTorch)
        - Or use snowboy or similar library
        
        Args:
            audio_chunk: Raw audio bytes from microphone
            
        Returns:
            True if wake word detected, False otherwise
        """
        try:
            # Check cooldown period
            current_time = time.time()
            if current_time - self.last_wake_word_time < self.wake_word_cooldown:
                return False
            
            # Validate audio chunk
            if not audio_chunk or len(audio_chunk) == 0:
                return False
            
            # Convert audio bytes to numpy array
            audio_array = np.frombuffer(audio_chunk, dtype=np.int16)
            
            # Validate array
            if len(audio_array) == 0:
                return False
            
            # Calculate audio energy using helper method
            energy = self._calculate_energy(audio_chunk)
            if energy is None:
                energy = 0.0
            
            # Add to history
            self.energy_history.append(energy)
            
            # Track quiet periods (for better detection)
            is_quiet = energy < self.quiet_threshold
            self.quiet_history.append(is_quiet)
            
            # Debug logging (can be enabled for troubleshooting)
            if self.debug_mode and len(self.energy_history) % 50 == 0:
                print(f"Audio energy: {energy:.1f} (threshold: {self.energy_threshold:.1f}, quiet: {is_quiet})")
            
            # Check if we have enough history
            if len(self.energy_history) < 5:
                return False
            
            # IMPROVED DETECTION LOGIC:
            # 1. Require a period of quiet before speech (reduces false positives from continuous noise)
            # 2. Require sustained speech above threshold (not just a brief spike)
            # 3. Use moving average to smooth out noise
            
            # Check if we had quiet before (recent quiet period)
            recent_quiet = list(self.quiet_history)[-5:]
            had_quiet_before = sum(recent_quiet) >= 3  # At least 3 of last 5 chunks were quiet
            
            # Check if energy exceeds threshold (someone is speaking)
            if energy > self.energy_threshold:
                # Track when speech started
                if self.speech_start_time is None:
                    # Only start tracking if we had quiet before (reduces false triggers)
                    if had_quiet_before:
                        self.speech_start_time = current_time
                    else:
                        # No quiet before, probably continuous noise - ignore
                        return False
                else:
                    # Check if we've had sustained speech for minimum duration
                    speech_duration = current_time - self.speech_start_time
                    
                    if speech_duration >= self.min_speech_duration:
                        # Calculate average energy over recent chunks
                        recent_energies = list(self.energy_history)[-10:]  # Last 10 chunks
                        avg_recent_energy = np.mean(recent_energies)
                        
                        # Require sustained high energy (not just a spike)
                        if avg_recent_energy > self.energy_threshold:
                            # Valid trigger!
                            self.last_wake_word_time = current_time
                            self.speech_start_time = None
                            # Clear history to prevent immediate re-trigger
                            self.energy_history.clear()
                            self.quiet_history.clear()
                            print(f"Wake word triggered! (energy: {avg_recent_energy:.1f}, duration: {speech_duration:.2f}s)")
                            return True
            else:
                # Energy dropped below threshold - reset speech tracking
                if self.speech_start_time is not None:
                    # Speech was interrupted, reset
                    self.speech_start_time = None
            
            return False
        
        except Exception as e:
            # If there's an error, log it but don't crash
            if self.debug_mode:
                print(f"Error in wake-word detection: {e}")
            return False
    
    def __del__(self):
        """Cleanup on deletion."""
        self.stop_listening()
        if hasattr(self, 'audio'):
            try:
                self.audio.terminate()
            except Exception:
                pass


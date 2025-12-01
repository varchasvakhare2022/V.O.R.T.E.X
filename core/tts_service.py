"""
Text-to-Speech Service.
Provides non-blocking TTS functionality using pyttsx3.
Runs in background thread to keep GUI responsive.
"""

import logging
import threading
import queue
from typing import Optional

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None
    logging.getLogger("VORTEX.TTS").warning("pyttsx3 not available, TTS will not work")


class TTSService:
    """
    Text-to-Speech service with non-blocking speech output.
    Handles multiple speak requests sequentially in a background thread.
    """
    
    def __init__(self):
        """Initialize TTS service with pyttsx3 engine."""
        self.logger = logging.getLogger("VORTEX.TTS")
        self.engine = None
        self.speech_queue = queue.Queue()
        self.speech_thread = None
        self.is_running = False
        self.lock = threading.Lock()
        
        self._initialize_engine()
        self._start_speech_thread()
    
    def _initialize_engine(self):
        """Initialize pyttsx3 TTS engine."""
        if pyttsx3 is None:
            self.logger.error("pyttsx3 library not installed")
            return
        
        try:
            self.engine = pyttsx3.init()
            
            # Configure voice properties (optional customization)
            # You can adjust rate, volume, and voice selection here
            voices = self.engine.getProperty('voices')
            if voices:
                # Try to use a more natural-sounding voice if available
                # On Windows, this might be a SAPI5 voice
                self.engine.setProperty('voice', voices[0].id)
            
            # Set speech rate (words per minute, default is usually 200)
            self.engine.setProperty('rate', 150)
            
            # Set volume (0.0 to 1.0)
            self.engine.setProperty('volume', 0.9)
            
            self.logger.info("TTS engine initialized successfully")
        
        except Exception as e:
            self.logger.error(f"Failed to initialize TTS engine: {e}", exc_info=True)
            self.engine = None
    
    def _start_speech_thread(self):
        """Start background thread for speech synthesis."""
        if self.speech_thread and self.speech_thread.is_alive():
            return
        
        with self.lock:
            self.is_running = True
        
        self.speech_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self.speech_thread.start()
        self.logger.debug("TTS speech thread started")
    
    def _speech_worker(self):
        """
        Background worker thread that processes speech queue.
        Handles multiple speak requests sequentially.
        """
        while self.is_running:
            try:
                # Get next text to speak from queue (with timeout to check is_running)
                try:
                    text = self.speech_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                if text is None:  # Exit signal
                    break
                
                if not self.engine:
                    self.logger.warning("TTS engine not available, skipping speech")
                    continue
                
                # Speak the text (this may block, but it's in a separate thread)
                try:
                    self.logger.debug(f"Speaking: '{text[:50]}...'")  # Log first 50 chars
                    self.engine.say(text)
                    self.engine.runAndWait()
                    self.logger.debug("Speech completed")
                
                except Exception as e:
                    self.logger.error(f"Error during speech synthesis: {e}", exc_info=True)
                
                finally:
                    self.speech_queue.task_done()
            
            except Exception as e:
                self.logger.error(f"Error in speech worker thread: {e}", exc_info=True)
                continue
    
    def speak(self, text: str) -> None:
        """
        Queue text for speech synthesis (non-blocking).
        Multiple calls will be processed sequentially.
        
        Args:
            text: Text string to speak
        """
        if not text or not text.strip():
            self.logger.warning("Empty text provided to speak()")
            return
        
        if not self.engine:
            self.logger.error("TTS engine not initialized, cannot speak")
            return
        
        try:
            self.speech_queue.put(text.strip())
            self.logger.debug(f"Text queued for speech: '{text[:50]}...'")
        
        except Exception as e:
            self.logger.error(f"Error queueing text for speech: {e}", exc_info=True)
    
    def stop(self):
        """Stop current speech and clear queue."""
        try:
            # Clear the queue
            while not self.speech_queue.empty():
                try:
                    self.speech_queue.get_nowait()
                except queue.Empty:
                    break
            
            # Stop the engine if it's speaking
            if self.engine:
                self.engine.stop()
            
            self.logger.info("TTS stopped and queue cleared")
        
        except Exception as e:
            self.logger.error(f"Error stopping TTS: {e}", exc_info=True)
    
    def wait_for_completion(self, timeout: Optional[float] = None):
        """
        Wait for all queued speech to complete.
        
        Args:
            timeout: Maximum time to wait in seconds. None for no timeout.
        """
        try:
            self.speech_queue.join()
            self.logger.debug("All queued speech completed")
        except Exception as e:
            self.logger.error(f"Error waiting for speech completion: {e}", exc_info=True)
    
    def shutdown(self):
        """Shutdown TTS service and clean up resources."""
        with self.lock:
            self.is_running = False
        
        # Signal thread to exit
        self.speech_queue.put(None)
        
        # Stop engine
        if self.engine:
            try:
                self.engine.stop()
            except Exception:
                pass
        
        # Wait for thread to finish
        if self.speech_thread and self.speech_thread.is_alive():
            self.speech_thread.join(timeout=2.0)
        
        self.logger.info("TTS service shut down")
    
    def __del__(self):
        """Cleanup on deletion."""
        try:
            self.shutdown()
        except Exception:
            pass


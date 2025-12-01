"""
Main VORTEX orchestrator class.
Coordinates all components: audio, speech, commands, and UI.
Wires backend services to the PyQt6 frontend.
"""

import logging
import threading
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from core.audio_manager import AudioManager
from core.stt_service import STTService
from core.tts_service import TTSService
from core.speaker_verification import SpeakerVerifier
from core.command_processor import CommandProcessor, CommandType
from core.app_launcher import AppLauncher
from core.config import Config


class VORTEX(QObject):
    """
    Main VORTEX application orchestrator.
    Coordinates all services and wires them to the GUI.
    """
    
    # Signals for GUI updates (thread-safe)
    status_update = pyqtSignal(str)
    message_update = pyqtSignal(str)
    listening_update = pyqtSignal(bool)
    owner_status_update = pyqtSignal(bool)
    
    def __init__(self, main_window, config: Config = None):
        """
        Initialize VORTEX components.
        
        Args:
            main_window: MainWindow instance for GUI updates
            config: Configuration object (uses default if None)
        """
        super().__init__()
        self.logger = logging.getLogger("VORTEX")
        self.main_window = main_window
        
        # Load configuration
        if config is None:
            from core.config import Config
            config = Config()
        self.config = config
        
        # Initialize services
        self.logger.info("Initializing VORTEX services...")
        
        # Initialize AudioManager with energy threshold from config
        energy_threshold = config.get("audio.wake_word_energy_threshold", 500.0)
        self.audio_manager = AudioManager(energy_threshold=energy_threshold)
        self.stt_service = STTService()
        self.tts_service = TTSService()
        self.speaker_verifier = SpeakerVerifier(
            voice_profile_path=config.voice_profile_path,
            test_mode=config.speaker_test_mode
        )
        self.speaker_verifier.set_similarity_threshold(config.speaker_similarity_threshold)
        
        self.app_launcher = AppLauncher()
        # Load app mappings from config
        for app_name, app_path in config.app_paths.items():
            is_fullscreen = app_name in config.fullscreen_apps
            self.app_launcher.add_app_mapping(app_name, app_path, is_fullscreen)
        
        self.command_processor = CommandProcessor(self.tts_service, self.app_launcher)
        
        # Wire callbacks
        self._setup_callbacks()
        
        # Connect signals to GUI
        self._connect_signals()
        
        # Connect audio visualizer
        self._connect_audio_visualizer()
        
        # Test mode: simulate wake-word with button/key
        self.test_mode = True
        self.test_timer = None
        
        self.logger.info("VORTEX services initialized")
    
    def _setup_callbacks(self):
        """Set up callbacks between services."""
        # AudioManager callbacks
        self.audio_manager.set_wake_word_callback(self._on_wake_word_detected)
        self.audio_manager.set_command_audio_callback(self._on_command_audio_received)
        
        # CommandProcessor GUI callback
        self.command_processor.set_gui_message_callback(self._send_message_to_gui)
        
        # AppLauncher window callbacks
        self.app_launcher.set_window_callbacks(
            self._minimize_window,
            self._restore_window,
            self._embed_app_window
        )
        
        self.logger.debug("Callbacks configured")
    
    def _connect_signals(self):
        """Connect signals to GUI slots."""
        self.status_update.connect(self.main_window.set_status)
        self.message_update.connect(self.main_window.append_system_message)
        self.listening_update.connect(self.main_window.indicate_listening)
        self.owner_status_update.connect(self.main_window.set_owner_status)
        
        self.logger.debug("Signals connected to GUI")
    
    def _connect_audio_visualizer(self):
        """Connect audio energy updates to visualizer."""
        if hasattr(self.main_window, 'audio_visualizer'):
            # Set callback to update visualizer
            self.audio_manager.set_energy_callback(
                lambda energy: self.main_window.audio_visualizer.energy_update.emit(energy)
            )
            self.logger.debug("Audio visualizer connected")
    
    def start(self):
        """Start the VORTEX application."""
        self.logger.info("Starting VORTEX...")
        
        # Start audio manager
        try:
            self.audio_manager.start_listening()
            self.logger.info("AudioManager started")
        except Exception as e:
            self.logger.error(f"Failed to start AudioManager: {e}", exc_info=True)
            self._send_message_to_gui("ERROR: Failed to start audio capture")
            return
        
        # Update GUI
        self.listening_update.emit(True)
        self.status_update.emit("Listening for wake word...")
        self._send_message_to_gui("VORTEX active. Listening for wake word 'Vortex'...")
        
        # Set up test mode trigger (temporary for testing)
        if self.test_mode:
            self._setup_test_trigger()
        
        self.logger.info("VORTEX started successfully")
    
    def stop(self):
        """Stop the VORTEX application."""
        self.logger.info("Stopping VORTEX...")
        
        # Stop audio manager
        try:
            self.audio_manager.stop_listening()
        except Exception as e:
            self.logger.error(f"Error stopping AudioManager: {e}", exc_info=True)
        
        # Shutdown TTS
        try:
            self.tts_service.shutdown()
        except Exception as e:
            self.logger.error(f"Error shutting down TTS: {e}", exc_info=True)
        
        self.listening_update.emit(False)
        self.status_update.emit("Stopped")
        self.logger.info("VORTEX stopped")
    
    def _setup_test_trigger(self):
        """
        Set up test trigger for simulating wake-word detection.
        Adds a button to the GUI for testing.
        """
        from PyQt6.QtWidgets import QPushButton
        from PyQt6.QtGui import QKeySequence, QShortcut
        
        # Add test button to status bar
        test_button = QPushButton("🔴 Simulate Wake Word")
        test_button.setStyleSheet("""
            QPushButton {
                background-color: #ff0000;
                color: white;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #ff3333;
            }
        """)
        test_button.clicked.connect(self._simulate_wake_word)
        self.main_window.statusBar().addWidget(test_button)
        
        # Add keyboard shortcut (Space bar)
        shortcut = QShortcut(QKeySequence("Space"), self.main_window)
        shortcut.activated.connect(self._simulate_wake_word)
        
        self.logger.info("Test trigger configured: Click button or press SPACE to simulate wake word")
    
    def _simulate_wake_word(self):
        """
        Simulate wake-word detection for testing.
        This will trigger the command recording flow.
        """
        self.logger.info("TEST: Simulating wake-word detection")
        self._on_wake_word_detected()
    
    def _on_wake_word_detected(self):
        """
        Callback when wake word "Vortex" is detected.
        Updates GUI and prepares for command recording.
        """
        self.logger.info("Wake word 'Vortex' detected")
        
        # Update GUI
        self.listening_update.emit(False)
        self.status_update.emit("Wake word detected. Recording command...")
        self._send_message_to_gui("Wake word detected. Listening for command...")
        
        # AudioManager will automatically start recording command audio
        # and call _on_command_audio_received when done
    
    def _on_command_audio_received(self, audio_data: bytes):
        """
        Callback when command audio has been recorded.
        Processes the audio through speaker verification and STT.
        
        Args:
            audio_data: Raw audio bytes of the command
        """
        self.logger.info(f"Command audio received: {len(audio_data)} bytes")
        self.status_update.emit("Processing command...")
        
        # Process in background thread to avoid blocking GUI
        thread = threading.Thread(
            target=self._process_command_audio,
            args=(audio_data,),
            daemon=True
        )
        thread.start()
    
    def _process_command_audio(self, audio_data: bytes):
        """
        Process command audio in background thread.
        Performs speaker verification and STT, then executes command.
        
        Args:
            audio_data: Raw audio bytes
        """
        try:
            self.logger.info("Processing command audio (speaker verification + STT)...")
            
            # Step 1: Speaker verification
            self.status_update.emit("Verifying speaker...")
            is_owner = self.speaker_verifier.verify_speaker(audio_data)
            
            self.logger.info(f"Speaker verification result: {'OWNER' if is_owner else 'INTRUDER'}")
            self.owner_status_update.emit(is_owner)
            
            if not is_owner:
                # Intruder detected - handle alert
                self.logger.warning("INTRUDER DETECTED - Access denied")
                self._handle_intruder_alert()
                return
            
            # Step 2: Speech-to-text
            self.status_update.emit("Transcribing command...")
            self.logger.info("Transcribing audio to text...")
            command_text = self.stt_service.transcribe_audio(audio_data)
            
            if not command_text:
                self.logger.warning("STT returned empty text")
                self.status_update.emit("Could not understand command")
                self._send_message_to_gui("ERROR: Could not understand command")
                self.tts_service.speak("I didn't catch that. Please try again.")
                self.listening_update.emit(True)
                return
            
            self.logger.info(f"Transcribed command: '{command_text}'")
            
            # Step 3: Display user command in GUI
            self.main_window.append_user_command(command_text)
            
            # Step 4: Process command
            self.status_update.emit("Executing command...")
            self.logger.info(f"Processing command: {command_text}")
            
            result = self.command_processor.process_command(command_text, is_owner=True)
            
            # Step 5: Update GUI with result
            if result.message:
                self._send_message_to_gui(result.message)
            
            # Step 6: Log result
            self.logger.info(f"Command processed: type={result.command_type}, success={result.success}")
            
            # Step 7: Resume listening
            self.status_update.emit("Ready")
            self.listening_update.emit(True)
            self._send_message_to_gui("Ready for next command. Say 'Vortex' to activate.")
        
        except Exception as e:
            self.logger.error(f"Error processing command audio: {e}", exc_info=True)
            self.status_update.emit("Error processing command")
            self._send_message_to_gui(f"ERROR: {str(e)}")
            self.tts_service.speak("An error occurred while processing your command.")
            self.listening_update.emit(True)
    
    def _handle_intruder_alert(self):
        """Handle intruder alert when speaker verification fails."""
        self.logger.warning("Handling intruder alert")
        
        # Update GUI
        self.main_window.show_intruder_alert()
        self.status_update.emit("INTRUDER DETECTED")
        
        # Speak alert
        self.tts_service.speak("Intruder alert. Access denied.")
        
        # Resume listening after alert
        self.listening_update.emit(True)
        self.status_update.emit("Listening for wake word...")
    
    def _send_message_to_gui(self, message: str):
        """
        Thread-safe method to send message to GUI.
        
        Args:
            message: Message text
        """
        # Use signal for thread-safe GUI update
        self.message_update.emit(message)
    
    def _minimize_window(self):
        """Minimize VORTEX window (called by AppLauncher)."""
        self.logger.info("Minimizing VORTEX window")
        if self.main_window:
            self.main_window.showMinimized()
    
    def _restore_window(self):
        """Restore VORTEX window (called by AppLauncher)."""
        self.logger.info("Restoring VORTEX window")
        if self.main_window:
            self.main_window.showFullScreen()
            self.main_window.raise_()
            self.main_window.activateWindow()
    
    def _embed_app_window(self, hwnd: int) -> bool:
        """
        Embed an app window into VORTEX (called by AppLauncher).
        
        Args:
            hwnd: Windows handle of the window to embed
            
        Returns:
            True if embedding successful, False otherwise
        """
        self.logger.info(f"Embedding app window: HWND={hwnd}")
        if self.main_window:
            return self.main_window.embed_app_window(hwnd)
        return False

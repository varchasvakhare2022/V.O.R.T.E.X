"""
VORTEX - Voice-Oriented Responsive Terminal EXecutive
Main entry point for the application.

═══════════════════════════════════════════════════════════════════════════
APPLICATION FLOW:
═══════════════════════════════════════════════════════════════════════════

1. INITIALIZATION PHASE:
   ├─> Setup logging (console + file)
   ├─> Load configuration from config.json
   ├─> Create QApplication (PyQt6)
   ├─> Create MainWindow (fullscreen UI)
   └─> Create VORTEX controller (orchestrates all services)

2. SERVICE INITIALIZATION:
   ├─> AudioManager: Starts continuous microphone capture
   ├─> STTService: Speech-to-text (stub/real implementation)
   ├─> TTSService: Text-to-speech engine
   ├─> SpeakerVerifier: Voice verification (test/production mode)
   ├─> CommandProcessor: Command parsing and execution
   └─> AppLauncher: Application launching and window management

3. RUNTIME FLOW:
   └─> AudioManager continuously listens for wake word "Vortex"
       ├─> Wake word detected → Start recording command audio (5 seconds)
       ├─> Command audio received → Process in background thread:
       │   ├─> SpeakerVerifier.verify_speaker() → Check if owner
       │   │   ├─> If INTRUDER → Alert + Ignore command
       │   │   └─> If OWNER → Continue
       │   ├─> STTService.transcribe_audio() → Convert to text
       │   ├─> CommandProcessor.process_command() → Parse and execute
       │   │   ├─> Parse command type (OPEN_APP, TIME_QUERY, etc.)
       │   │   ├─> Execute action (launch app, query time, etc.)
       │   │   ├─> TTSService.speak() → Speak response
       │   │   └─> Update GUI with results
       │   └─> Resume listening for next wake word
       └─> Loop continues...

4. GUI UPDATES:
   └─> All GUI updates use PyQt6 signals (thread-safe)
       ├─> status_update → Status bar messages
       ├─> message_update → System messages in console
       ├─> listening_update → Listening/Idle indicator
       └─> owner_status_update → Owner/Intruder indicator

5. APPLICATION SHUTDOWN:
   └─> User closes window or Ctrl+C
       ├─> Stop AudioManager
       ├─> Shutdown TTSService
       └─> Clean up resources

═══════════════════════════════════════════════════════════════════════════
"""

import sys
import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication

# Ensure required directories exist
os.makedirs('data/logs', exist_ok=True)
os.makedirs('data/voice_profile', exist_ok=True)

# Import configuration
from core.config import Config

# Initialize configuration (must be before other imports that use it)
config = Config()

# Setup logging with proper configuration
def setup_logging():
    """Configure logging for VORTEX."""
    log_level = logging.INFO
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Get log file path from config
    logs_path = config.logs_path
    os.makedirs(logs_path, exist_ok=True)
    log_file = os.path.join(logs_path, 'vortex.log')
    
    # Create formatters
    formatter = logging.Formatter(log_format, date_format)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # File handler
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()  # Remove default handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    logging.info("=" * 70)
    logging.info("VORTEX - Voice-Oriented Responsive Terminal EXecutive")
    logging.info("=" * 70)
    logging.info(f"Logging initialized - Console + File: {log_file}")

# Setup logging before importing other modules
setup_logging()

# Now import application modules
from ui.main_window import MainWindow
from core.vortex import VORTEX


def main():
    """
    Main entry point for VORTEX application.
    
    Initializes all components and starts the application event loop.
    """
    logger = logging.getLogger("VORTEX.Main")
    
    try:
        # Create QApplication
        app = QApplication(sys.argv)
        app.setApplicationName("VORTEX")
        app.setApplicationDisplayName("VORTEX - Voice-Oriented Responsive Terminal EXecutive")
        
        logger.info("QApplication created")
        
        # Create main window
        logger.info("Creating MainWindow...")
        window = MainWindow()
        window.show()
        logger.info("MainWindow created and displayed")
        
        # Create and start VORTEX controller
        logger.info("Initializing VORTEX controller...")
        vortex = VORTEX(window, config)
        logger.info("VORTEX controller initialized")
        
        # Start VORTEX services
        logger.info("Starting VORTEX services...")
        vortex.start()
        logger.info("VORTEX services started")
        
        # Handle application shutdown
        def on_shutdown():
            logger.info("Application shutting down...")
            vortex.stop()
            logger.info("Shutdown complete")
        
        app.aboutToQuit.connect(on_shutdown)
        
        # Start Qt event loop
        logger.info("Starting Qt event loop...")
        logger.info("VORTEX is now running. Say 'Vortex' to activate (or press SPACE for test mode)")
        exit_code = app.exec()
        
        logger.info(f"Application exited with code: {exit_code}")
        return exit_code
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user (Ctrl+C)")
        return 0
    except Exception as e:
        logger.critical(f"Fatal error in main: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

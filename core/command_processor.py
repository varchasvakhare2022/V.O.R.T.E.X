"""
Command Processor.
Parses voice commands and executes appropriate actions.
Handles intruder alerts and coordinates with TTS and AppLauncher.
"""

import logging
from enum import Enum
from typing import Optional, Callable
from datetime import datetime

from core.tts_service import TTSService
from core.app_launcher import AppLauncher


class CommandType(Enum):
    """Types of commands that can be processed."""
    OPEN_APP = "open_app"
    OPEN_FULLSCREEN_APP = "open_fullscreen_app"
    RESTORE_VORTEX = "restore_vortex"
    SHOW_MESSAGE = "show_message"
    INTRUDER_ALERT = "intruder_alert"
    UNKNOWN = "unknown"
    TIME_QUERY = "time_query"


class CommandResult:
    """Result of command processing."""
    
    def __init__(self, command_type: CommandType, success: bool, 
                 message: str = "", app_name: str = ""):
        """
        Initialize command result.
        
        Args:
            command_type: Type of command that was processed
            success: Whether the command was executed successfully
            message: Response message for user/GUI
            app_name: Name of app if applicable
        """
        self.command_type = command_type
        self.success = success
        self.message = message
        self.app_name = app_name


class CommandProcessor:
    """
    Processes voice commands and executes appropriate actions.
    Coordinates with TTS, AppLauncher, and GUI.
    """
    
    def __init__(self, tts_service: TTSService, app_launcher: AppLauncher):
        """
        Initialize command processor.
        
        Args:
            tts_service: TTS service for speaking responses
            app_launcher: App launcher for executing app commands
        """
        self.logger = logging.getLogger("VORTEX.CommandProcessor")
        self.tts_service = tts_service
        self.app_launcher = app_launcher
        
        # Callback for sending messages to GUI
        self.gui_message_callback: Optional[Callable[[str], None]] = None
    
    def set_gui_message_callback(self, callback: Callable[[str], None]):
        """
        Set callback for sending text messages to GUI.
        
        Args:
            callback: Function that takes a message string and displays it in GUI
        """
        self.gui_message_callback = callback
    
    def process_command(self, text: str, is_owner: bool = True) -> CommandResult:
        """
        Process a voice command.
        
        Args:
            text: Transcribed command text
            is_owner: Whether the speaker is verified as the owner
            
        Returns:
            CommandResult object with processing details
        """
        if not text or not text.strip():
            self.logger.warning("Empty command text received")
            return CommandResult(CommandType.UNKNOWN, False, "Empty command")
        
        text_lower = text.strip().lower()
        self.logger.info(f"Processing command: '{text}' (owner: {is_owner})")
        
        # Check for intruder (unauthorized speaker)
        if not is_owner:
            return self._handle_intruder_alert()
        
        # Parse and execute command
        command_type = self._parse_command_type(text_lower)
        
        if command_type == CommandType.OPEN_APP:
            return self._handle_open_app(text_lower)
        
        elif command_type == CommandType.OPEN_FULLSCREEN_APP:
            return self._handle_open_fullscreen_app(text_lower)
        
        elif command_type == CommandType.RESTORE_VORTEX:
            return self._handle_restore_vortex()
        
        elif command_type == CommandType.TIME_QUERY:
            return self._handle_time_query()
        
        elif command_type == CommandType.UNKNOWN:
            return self._handle_unknown_command(text)
        
        else:
            return CommandResult(CommandType.UNKNOWN, False, f"Unhandled command type: {command_type}")
    
    def _parse_command_type(self, text: str) -> CommandType:
        """
        Parse command text to determine command type.
        Uses simple rule-based keyword matching.
        
        Args:
            text: Lowercase command text
            
        Returns:
            CommandType enum value
        """
        # Restore VORTEX commands
        if any(phrase in text for phrase in ['vortex come back', 'come back', 'restore vortex', 'show vortex']):
            return CommandType.RESTORE_VORTEX
        
        # Time queries
        if any(phrase in text for phrase in ['what time', 'what\'s the time', 'time is it', 'current time']):
            return CommandType.TIME_QUERY
        
        # App opening commands
        if 'open' in text:
            # Check if it's a fullscreen app
            app_name = self._extract_app_name(text)
            if app_name and self.app_launcher.is_fullscreen_app(app_name):
                return CommandType.OPEN_FULLSCREEN_APP
            else:
                return CommandType.OPEN_APP
        
        return CommandType.UNKNOWN
    
    def _extract_app_name(self, text: str) -> Optional[str]:
        """
        Extract application name from command text.
        
        Args:
            text: Lowercase command text
            
        Returns:
            App name string or None if not found
        """
        # Remove common prefixes
        prefixes = ['open', 'launch', 'start', 'run']
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break
        
        # Common app name mappings
        app_mappings = {
            'notepad': 'notepad',
            'calculator': 'calculator',
            'calc': 'calculator',
            'chrome': 'chrome',
            'google chrome': 'chrome',
            'firefox': 'firefox',
            'valorant': 'valorant',
            'game': 'valorant',  # Generic "game" might map to valorant
            'games': 'valorant',
        }
        
        # Direct match
        if text in app_mappings:
            return app_mappings[text]
        
        # Partial match
        for key, value in app_mappings.items():
            if key in text:
                return value
        
        # Return cleaned text as app name
        return text.strip() if text.strip() else None
    
    def _handle_open_app(self, text: str) -> CommandResult:
        """Handle opening a normal (embedded) application."""
        app_name = self._extract_app_name(text)
        
        if not app_name:
            message = "I didn't understand which app to open."
            self._send_to_gui(message)
            self.tts_service.speak(message)
            return CommandResult(CommandType.OPEN_APP, False, message)
        
        self.logger.info(f"Opening app: {app_name}")
        success = self.app_launcher.launch_embedded_app(app_name)
        
        if success:
            message = f"Opening {app_name}."
            self._send_to_gui(message)
            self.tts_service.speak(message)
            return CommandResult(CommandType.OPEN_APP, True, message, app_name)
        else:
            message = f"Sorry, I couldn't open {app_name}."
            self._send_to_gui(message)
            self.tts_service.speak(message)
            return CommandResult(CommandType.OPEN_APP, False, message, app_name)
    
    def _handle_open_fullscreen_app(self, text: str) -> CommandResult:
        """Handle opening a fullscreen application."""
        app_name = self._extract_app_name(text)
        
        if not app_name:
            message = "I didn't understand which app to open."
            self._send_to_gui(message)
            self.tts_service.speak(message)
            return CommandResult(CommandType.OPEN_FULLSCREEN_APP, False, message)
        
        self.logger.info(f"Opening fullscreen app: {app_name}")
        success = self.app_launcher.launch_fullscreen_app(app_name)
        
        if success:
            message = f"Opening {app_name}. VORTEX minimized."
            self._send_to_gui(message)
            self.tts_service.speak(message)
            return CommandResult(CommandType.OPEN_FULLSCREEN_APP, True, message, app_name)
        else:
            message = f"Sorry, I couldn't open {app_name}."
            self._send_to_gui(message)
            self.tts_service.speak(message)
            return CommandResult(CommandType.OPEN_FULLSCREEN_APP, False, message, app_name)
    
    def _handle_restore_vortex(self) -> CommandResult:
        """Handle restoring VORTEX window."""
        self.logger.info("Restoring VORTEX window")
        self.app_launcher.restore_vortex_window()
        
        message = "VORTEX restored."
        self._send_to_gui(message)
        self.tts_service.speak(message)
        
        return CommandResult(CommandType.RESTORE_VORTEX, True, message)
    
    def _handle_time_query(self) -> CommandResult:
        """Handle time query commands."""
        now = datetime.now()
        time_str = now.strftime("%I:%M %p")  # e.g., "03:45 PM"
        
        message = f"The current time is {time_str}."
        self._send_to_gui(message)
        self.tts_service.speak(message)
        
        return CommandResult(CommandType.TIME_QUERY, True, message)
    
    def _handle_unknown_command(self, text: str) -> CommandResult:
        """Handle unrecognized commands."""
        message = f"I didn't understand: {text}"
        self.logger.warning(f"Unknown command: {text}")
        self._send_to_gui(message)
        self.tts_service.speak("I didn't understand that command.")
        
        return CommandResult(CommandType.UNKNOWN, False, message)
    
    def _handle_intruder_alert(self) -> CommandResult:
        """
        Handle intruder alert when speaker verification fails.
        
        Returns:
            CommandResult with INTRUDER_ALERT type
        """
        self.logger.warning("INTRUDER ALERT: Unauthorized speaker detected!")
        
        alert_message = "Intruder alert. Access denied."
        self._send_to_gui(alert_message)
        self.tts_service.speak(alert_message)
        
        return CommandResult(CommandType.INTRUDER_ALERT, False, alert_message)
    
    def _send_to_gui(self, message: str):
        """
        Send message to GUI via callback.
        
        Args:
            message: Message text to display
        """
        if self.gui_message_callback:
            try:
                self.gui_message_callback(message)
            except Exception as e:
                self.logger.error(f"Error sending message to GUI: {e}", exc_info=True)
        else:
            self.logger.debug(f"GUI callback not set, message: {message}")


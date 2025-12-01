"""
Main fullscreen window for VORTEX.
Tech-style dark UI with neon accents.
"""

import logging
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QSplitter, QStatusBar, QPushButton, QLabel)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut

from ui.widgets.command_log import CommandLog
from ui.widgets.response_display import ResponseDisplay
from ui.widgets.status_indicator import StatusIndicator
from ui.widgets.audio_visualizer import AudioVisualizer
from ui.styles.dark_theme import DarkTheme


class MainWindow(QMainWindow):
    """
    Main fullscreen VORTEX window.
    Provides console-style interface with command log and response display.
    """
    
    # Signals for backend communication (if using signals/slots)
    command_received = pyqtSignal(str)
    
    def __init__(self):
        """Initialize main window."""
        super().__init__()
        self.logger = logging.getLogger("VORTEX.UI")
        self.theme = DarkTheme()
        self.setup_ui()
        self.setup_mock_backend()  # For testing
        
        # Apply theme
        self.setStyleSheet(self.theme.get_stylesheet())
    
    def setup_ui(self):
        """Set up the user interface."""
        # Set window properties
        self.setWindowTitle("VORTEX - Voice-Oriented Responsive Terminal EXecutive")
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel: Command log
        self.command_log = CommandLog()
        self.command_log.setMinimumWidth(300)
        self.command_log.setMaximumWidth(400)
        splitter.addWidget(self.command_log)
        
        # Center panel: Container for response display and embedded apps
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(10)
        
        # Audio visualizer (voice bar)
        self.audio_visualizer = AudioVisualizer()
        center_layout.addWidget(self.audio_visualizer)
        
        # Response display (always visible)
        self.response_display = ResponseDisplay()
        self.response_display.setMinimumHeight(200)
        center_layout.addWidget(self.response_display, stretch=1)
        
        # Embedded app container (for apps like Notepad)
        self.embedded_app_container = QWidget()
        self.embedded_app_container.setMinimumHeight(400)
        self.embedded_app_container.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border: 2px solid #00ff00;
                border-radius: 4px;
            }
        """)
        self.embedded_app_container.hide()  # Hidden by default
        center_layout.addWidget(self.embedded_app_container, stretch=2)
        
        splitter.addWidget(center_container)
        
        # Set splitter proportions (30% left, 70% center)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        
        main_layout.addWidget(splitter)
        
        # Track embedded app
        self.embedded_app_hwnd = None
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Add status indicator to status bar
        self.status_indicator = StatusIndicator()
        self.status_bar.addPermanentWidget(self.status_indicator)
        
        # Add welcome message
        self.response_display.append_system_message("VORTEX initialized. Ready for commands.")
        self.response_display.append_system_message("Say 'Vortex' to activate.")
        
        # Keyboard shortcuts
        self.setup_shortcuts()
    
    def setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        # ESC to exit fullscreen (for testing)
        exit_fullscreen = QShortcut(QKeySequence("Escape"), self)
        exit_fullscreen.activated.connect(self.toggle_fullscreen)
        
        # F11 to toggle fullscreen
        toggle_fullscreen = QShortcut(QKeySequence("F11"), self)
        toggle_fullscreen.activated.connect(self.toggle_fullscreen)
    
    def setup_mock_backend(self):
        """
        Set up mock backend for testing UI.
        Simulates commands and responses.
        """
        self.mock_timer = QTimer()
        self.mock_timer.timeout.connect(self._mock_tick)
        self.mock_counter = 0
        
        # Add test button (can be removed later)
        test_button = QPushButton("Test UI (Mock Commands)")
        test_button.clicked.connect(self._run_mock_test)
        self.status_bar.addWidget(test_button)
    
    def _run_mock_test(self):
        """Run a mock test sequence."""
        self.mock_counter = 0
        self.mock_timer.start(2000)  # Every 2 seconds
    
    def _mock_tick(self):
        """Mock backend tick - simulates commands."""
        self.mock_counter += 1
        
        if self.mock_counter == 1:
            self.append_user_command("open notepad")
            self.set_status("Processing command...")
            self.indicate_listening(False)
        
        elif self.mock_counter == 2:
            self.append_system_message("Opening notepad...")
            self.set_status("Command executed")
        
        elif self.mock_counter == 3:
            self.append_user_command("what time is it")
            self.indicate_listening(True)
        
        elif self.mock_counter == 4:
            self.append_system_message("The current time is 3:45 PM.")
            self.set_status("Ready")
            self.indicate_listening(True)
        
        elif self.mock_counter == 5:
            self.append_user_command("open valorant")
            self.set_status("Launching fullscreen app...")
        
        elif self.mock_counter == 6:
            self.append_system_message("Opening valorant. VORTEX minimized.")
            self.set_status("Minimized")
            self.mock_timer.stop()
    
    def show_fullscreen(self):
        """Display window in fullscreen mode."""
        self.showFullScreen()
        self.logger.info("VORTEX window displayed in fullscreen")
    
    def get_embedded_app_container(self):
        """
        Get the widget container for embedded apps.
        
        Returns:
            QWidget container for embedded applications
        """
        return self.embedded_app_container
    
    def embed_app_window(self, hwnd: int) -> bool:
        """
        Embed an external window into the embedded app container.
        
        Args:
            hwnd: Windows handle of the window to embed
            
        Returns:
            True if embedding successful, False otherwise
        """
        try:
            from utils.windows_integration import WindowsIntegration
            
            win_integration = WindowsIntegration()
            container_hwnd = int(self.embedded_app_container.winId())
            
            # Embed the window
            if win_integration.embed_window(hwnd, container_hwnd):
                # Position window to fill container
                geometry = self.embedded_app_container.geometry()
                win_integration.position_window(
                    hwnd,
                    geometry.x(),
                    geometry.y(),
                    geometry.width(),
                    geometry.height()
                )
                
                # Show container
                self.embedded_app_container.show()
                self.embedded_app_hwnd = hwnd
                
                self.logger.info(f"Successfully embedded window {hwnd}")
                return True
            
            return False
        
        except Exception as e:
            self.logger.error(f"Error embedding app window: {e}", exc_info=True)
            return False
    
    def resizeEvent(self, event):
        """Handle window resize to reposition embedded app."""
        super().resizeEvent(event)
        
        # Reposition embedded app if present
        if self.embedded_app_hwnd and self.embedded_app_container.isVisible():
            try:
                from utils.windows_integration import WindowsIntegration
                win_integration = WindowsIntegration()
                
                geometry = self.embedded_app_container.geometry()
                win_integration.position_window(
                    self.embedded_app_hwnd,
                    geometry.x(),
                    geometry.y(),
                    geometry.width(),
                    geometry.height()
                )
            except Exception as e:
                self.logger.error(f"Error repositioning embedded app: {e}", exc_info=True)
    
    def showEvent(self, event):
        """Override showEvent to automatically go fullscreen."""
        super().showEvent(event)
        if event.spontaneous():
            return
        # Auto-fullscreen on first show
        self.show_fullscreen()
    
    def toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
    
    def append_system_message(self, text: str):
        """
        Append a system message to the response display.
        
        Args:
            text: Message text to display
        """
        self.response_display.append_system_message(text)
        self.logger.debug(f"System message: {text}")
    
    def append_user_command(self, text: str):
        """
        Append a user command to both command log and response display.
        
        Args:
            text: Command text
        """
        self.command_log.add_command(text)
        self.response_display.append_user_command(text)
        self.logger.debug(f"User command: {text}")
    
    def set_status(self, text: str):
        """
        Set status bar text.
        
        Args:
            text: Status text
        """
        self.status_bar.showMessage(text)
        self.logger.debug(f"Status: {text}")
    
    def indicate_listening(self, is_listening: bool):
        """
        Update listening status indicator.
        
        Args:
            is_listening: True if listening, False if idle
        """
        self.status_indicator.set_listening(is_listening)
        if is_listening:
            self.set_status("Listening for wake word...")
        else:
            self.set_status("Idle")
    
    def set_owner_status(self, is_owner: bool):
        """
        Update owner/intruder status indicator.
        
        Args:
            is_owner: True if owner, False if intruder
        """
        self.status_indicator.set_owner_status(is_owner)
        if not is_owner:
            self.append_error("INTRUDER ALERT - Access denied")
            self.set_status("INTRUDER DETECTED")
    
    def add_command_log(self, command: str):
        """
        Add command to log display (alias for append_user_command).
        
        Args:
            command: Command text
        """
        self.append_user_command(command)
    
    def add_response(self, response: str):
        """
        Add response to display (alias for append_system_message).
        
        Args:
            response: Response text
        """
        self.append_system_message(response)
    
    def show_intruder_alert(self):
        """Display intruder alert message."""
        self.set_owner_status(False)
        self.append_error("INTRUDER ALERT - Unauthorized access detected")
        self.append_error("Access denied. Command ignored.")
        self.set_status("INTRUDER DETECTED")

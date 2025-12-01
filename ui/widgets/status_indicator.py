"""
Status indicator widget.
Visual indicators for system status.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen


class StatusIndicator(QWidget):
    """Widget for displaying system status indicators."""
    
    def __init__(self, parent=None):
        """Initialize status indicator widget."""
        super().__init__(parent)
        self.setup_ui()
        self.listening_status = False
        self.owner_status = True  # Default to owner
    
    def setup_ui(self):
        """Set up the status indicator UI."""
        layout = QHBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Listening status
        self.listening_label = QLabel("● IDLE")
        self.listening_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        layout.addWidget(self.listening_label)
        
        # Owner/Intruder status
        self.owner_label = QLabel("● OWNER")
        self.owner_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        layout.addWidget(self.owner_label)
        
        layout.addStretch()
        
        self.setLayout(layout)
    
    def set_listening(self, is_listening: bool):
        """
        Update listening status indicator.
        
        Args:
            is_listening: True if listening, False if idle
        """
        self.listening_status = is_listening
        if is_listening:
            self.listening_label.setText("● LISTENING")
            self.listening_label.setStyleSheet(
                "font-weight: bold; font-size: 11pt; color: #00ff00;"
            )
        else:
            self.listening_label.setText("● IDLE")
            self.listening_label.setStyleSheet(
                "font-weight: bold; font-size: 11pt; color: #888888;"
            )
    
    def set_owner_status(self, is_owner: bool):
        """
        Update owner/intruder status indicator.
        
        Args:
            is_owner: True if owner, False if intruder
        """
        self.owner_status = is_owner
        if is_owner:
            self.owner_label.setText("● OWNER")
            self.owner_label.setStyleSheet(
                "font-weight: bold; font-size: 11pt; color: #00ff00;"
            )
        else:
            self.owner_label.setText("● INTRUDER")
            self.owner_label.setStyleSheet(
                "font-weight: bold; font-size: 11pt; color: #ff0000;"
            )
    
    def set_processing(self, is_processing: bool):
        """
        Update processing status indicator.
        (Can be extended if needed)
        
        Args:
            is_processing: True if processing
        """
        pass
    
    def set_error(self, has_error: bool):
        """
        Update error status indicator.
        (Can be extended if needed)
        
        Args:
            has_error: True if error occurred
        """
        pass

"""
Command log widget.
Displays animated command history in a scrollable list.
"""

from PyQt6.QtWidgets import QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor


class CommandLog(QListWidget):
    """Widget for displaying command logs with animation."""
    
    MAX_ITEMS = 50  # Maximum number of commands to keep
    
    def __init__(self, parent=None):
        """Initialize command log widget."""
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the command log UI."""
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.setSpacing(2)
    
    def add_command(self, command: str):
        """
        Add a command to the log with animation.
        
        Args:
            command: Command text to add
        """
        if not command:
            return
        
        # Create list item
        item = QListWidgetItem(f"> {command}")
        item.setForeground(QColor("#00ffff"))  # Cyan for user commands
        
        # Add to list
        self.insertItem(0, item)  # Insert at top
        
        # Limit number of items
        if self.count() > self.MAX_ITEMS:
            self.takeItem(self.MAX_ITEMS)
        
        # Auto-scroll to top
        self.scrollToTop()
    
    def clear(self):
        """Clear all command logs."""
        super().clear()

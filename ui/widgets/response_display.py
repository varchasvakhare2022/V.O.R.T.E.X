"""
Response display widget.
Shows VORTEX responses with console-style text display.
"""

from PyQt6.QtWidgets import QPlainTextEdit
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QTextCharFormat, QColor, QTextCursor
from datetime import datetime


class ResponseDisplay(QPlainTextEdit):
    """Widget for displaying VORTEX responses with console-style formatting."""
    
    MAX_LINES = 1000  # Maximum lines to keep
    
    def __init__(self, parent=None):
        """Initialize response display widget."""
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the response display UI."""
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setUndoRedoEnabled(False)
    
    def show_response(self, text: str, color: str = "#00ff00"):
        """
        Display response text with formatting.
        
        Args:
            text: Response text to display
            color: Text color (hex string)
        """
        if not text:
            return
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_text = f"[{timestamp}] {text}\n"
        
        # Create text format
        text_format = QTextCharFormat()
        text_format.setForeground(QColor(color))
        
        # Append text with formatting
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.setCharFormat(text_format)
        cursor.insertText(formatted_text)
        
        # Limit number of lines
        self._limit_lines()
        
        # Auto-scroll to bottom
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
    
    def append_system_message(self, text: str):
        """
        Append a system message (cyan color).
        
        Args:
            text: System message text
        """
        self.show_response(text, color="#00ffff")
    
    def append_user_command(self, text: str):
        """
        Append a user command (yellow color).
        
        Args:
            text: User command text
        """
        self.show_response(f"User: {text}", color="#ffff00")
    
    def append_error(self, text: str):
        """
        Append an error message (red color).
        
        Args:
            text: Error message text
        """
        self.show_response(f"ERROR: {text}", color="#ff0000")
    
    def _limit_lines(self):
        """Limit the number of lines in the display."""
        document = self.document()
        if document.blockCount() > self.MAX_LINES:
            cursor = QTextCursor(document)
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(QTextCursor.MoveOperation.Down, 
                             QTextCursor.MoveMode.MoveAnchor, 
                             document.blockCount() - self.MAX_LINES)
            cursor.movePosition(QTextCursor.MoveOperation.Start, 
                              QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
    
    def clear(self):
        """Clear response display."""
        super().clear()

"""
Dark tech-style theme for VORTEX UI.
Neon accents, hacker/Iron Man style.
"""


class DarkTheme:
    """Dark tech-style theme configuration."""
    
    # Color palette
    BACKGROUND_DARK = "#0a0a0a"
    BACKGROUND_MEDIUM = "#1a1a1a"
    BACKGROUND_LIGHT = "#2a2a2a"
    
    TEXT_PRIMARY = "#00ff00"  # Neon green
    TEXT_SECONDARY = "#00cc00"
    TEXT_MUTED = "#888888"
    
    ACCENT_CYAN = "#00ffff"
    ACCENT_BLUE = "#0088ff"
    ACCENT_PURPLE = "#aa00ff"
    
    BORDER_COLOR = "#333333"
    BORDER_NEON = "#00ff00"
    
    STATUS_LISTENING = "#00ff00"
    STATUS_IDLE = "#888888"
    STATUS_INTRUDER = "#ff0000"
    STATUS_OWNER = "#00ff00"
    
    def __init__(self):
        """Initialize theme."""
        pass
    
    def get_stylesheet(self) -> str:
        """
        Get Qt stylesheet for dark theme.
        
        Returns:
            CSS stylesheet string
        """
        return f"""
        QMainWindow {{
            background-color: {self.BACKGROUND_DARK};
            color: {self.TEXT_PRIMARY};
        }}
        
        QWidget {{
            background-color: {self.BACKGROUND_DARK};
            color: {self.TEXT_PRIMARY};
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 12pt;
        }}
        
        QTextEdit, QPlainTextEdit {{
            background-color: {self.BACKGROUND_MEDIUM};
            color: {self.TEXT_PRIMARY};
            border: 1px solid {self.BORDER_COLOR};
            border-radius: 4px;
            padding: 10px;
            selection-background-color: {self.ACCENT_CYAN};
        }}
        
        QListWidget {{
            background-color: {self.BACKGROUND_MEDIUM};
            color: {self.TEXT_PRIMARY};
            border: 1px solid {self.BORDER_COLOR};
            border-radius: 4px;
            padding: 5px;
        }}
        
        QListWidget::item {{
            padding: 5px;
            border-bottom: 1px solid {self.BORDER_COLOR};
        }}
        
        QListWidget::item:selected {{
            background-color: {self.ACCENT_BLUE};
            color: {self.BACKGROUND_DARK};
        }}
        
        QLabel {{
            background-color: transparent;
            color: {self.TEXT_PRIMARY};
        }}
        
        QStatusBar {{
            background-color: {self.BACKGROUND_MEDIUM};
            color: {self.TEXT_PRIMARY};
            border-top: 2px solid {self.BORDER_NEON};
            padding: 5px;
        }}
        
        QPushButton {{
            background-color: {self.BACKGROUND_LIGHT};
            color: {self.TEXT_PRIMARY};
            border: 1px solid {self.BORDER_NEON};
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
        }}
        
        QPushButton:hover {{
            background-color: {self.ACCENT_CYAN};
            color: {self.BACKGROUND_DARK};
        }}
        
        QPushButton:pressed {{
            background-color: {self.ACCENT_BLUE};
        }}
        """
    
    def get_colors(self) -> dict:
        """
        Get color palette for theme.
        
        Returns:
            Dictionary of color names to hex values
        """
        return {
            'background_dark': self.BACKGROUND_DARK,
            'background_medium': self.BACKGROUND_MEDIUM,
            'background_light': self.BACKGROUND_LIGHT,
            'text_primary': self.TEXT_PRIMARY,
            'text_secondary': self.TEXT_SECONDARY,
            'text_muted': self.TEXT_MUTED,
            'accent_cyan': self.ACCENT_CYAN,
            'accent_blue': self.ACCENT_BLUE,
            'accent_purple': self.ACCENT_PURPLE,
            'border_color': self.BORDER_COLOR,
            'border_neon': self.BORDER_NEON,
            'status_listening': self.STATUS_LISTENING,
            'status_idle': self.STATUS_IDLE,
            'status_intruder': self.STATUS_INTRUDER,
            'status_owner': self.STATUS_OWNER,
        }

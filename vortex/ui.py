# vortex/ui.py

from __future__ import annotations

from enum import Enum, auto

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QTextEdit,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QFrame,
)


# -----------------------------------------------------------------------------
# Theme enum
# -----------------------------------------------------------------------------

class VortexTheme(Enum):
    NORMAL = auto()
    SECURITY = auto()
    LOCKDOWN = auto()


# -----------------------------------------------------------------------------
# Main window
# -----------------------------------------------------------------------------

class VortexWindow(QMainWindow):
    """
    Main VORTEX UI window.

    Layout:
    - Top:  status bar with STATUS label
    - Center left:  console (dialog between YOU and VORTEX)
    - Center right: tabbed panel (Commands / Timeline / Memory)
    - Bottom: command input, Send button, Mic button

    Colors (only four):
    - Background: black (#000000)
    - Primary text: green (#00FF00)
    - Accent: blue (#00BFFF)
    - Security / error: red (#FF0033)
    """

    # Emitted when the user presses Enter or clicks Send
    command_entered = pyqtSignal(str)
    # Emitted when the user clicks the Mic button
    voice_listen_requested = pyqtSignal()

    GREEN = "#00FF00"
    BLUE = "#00BFFF"
    RED = "#FF0033"
    BLACK = "#000000"

    def __init__(self):
        super().__init__()

        self.setWindowTitle("V.O.R.T.E.X")
        # Start maximized by default
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

        central = QWidget(self)
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)

        # ---- Status bar ----------------------------------------------------
        self.status_frame = QFrame()
        self.status_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.status_frame.setObjectName("statusFrame")

        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(8, 4, 8, 4)
        status_layout.setSpacing(4)

        self.status_label = QLabel("STATUS: IDLE")
        self.status_label.setObjectName("statusLabel")

        status_layout.addWidget(self.status_label)
        status_layout.addStretch(1)

        root_layout.addWidget(self.status_frame)

        # ---- Center area ---------------------------------------------------
        center_frame = QFrame()
        center_frame.setObjectName("centerFrame")
        center_layout = QHBoxLayout(center_frame)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(6)

        # Left: console
        console_frame = QFrame()
        console_layout = QVBoxLayout(console_frame)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(0)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setObjectName("console")
        self.console.setAcceptRichText(True)

        console_layout.addWidget(self.console)

        # Right: tabs
        side_frame = QFrame()
        side_layout = QVBoxLayout(side_frame)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("sideTabs")

        # Commands tab: just a list of user commands
        self.commands_list = QListWidget()
        self.commands_list.setObjectName("commandsList")
        self.tabs.addTab(self.commands_list, "Commands")

        # Timeline tab: system events
        self.timeline_list = QListWidget()
        self.timeline_list.setObjectName("timelineList")
        self.tabs.addTab(self.timeline_list, "Timeline")

        # Memory tab: multi-line text
        self.memory_view = QTextEdit()
        self.memory_view.setReadOnly(True)
        self.memory_view.setObjectName("memoryView")
        self.tabs.addTab(self.memory_view, "Memory")

        side_layout.addWidget(self.tabs)

        center_layout.addWidget(console_frame, stretch=3)
        center_layout.addWidget(side_frame, stretch=1)

        root_layout.addWidget(center_frame, stretch=1)

        # ---- Bottom input bar ---------------------------------------------
        input_frame = QFrame()
        input_frame.setObjectName("inputFrame")
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(4, 4, 4, 4)
        input_layout.setSpacing(6)

        self.command_input = QLineEdit()
        self.command_input.setObjectName("commandInput")
        self.command_input.setPlaceholderText("Type a command for VORTEX and press Enter...")
        self.command_input.returnPressed.connect(self._on_return_pressed)

        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("sendButton")
        self.send_button.clicked.connect(self._on_send_clicked)

        self.mic_button = QPushButton("\u1F399")  # microphone icon-ish
        self.mic_button.setObjectName("micButton")
        self.mic_button.setText("🎙")
        self.mic_button.clicked.connect(self._on_mic_clicked)

        input_layout.addWidget(self.command_input, stretch=1)
        input_layout.addWidget(self.send_button)
        input_layout.addWidget(self.mic_button)

        root_layout.addWidget(input_frame)

        # Apply base style
        self._apply_theme_styles(VortexTheme.NORMAL)

    # ------------------------------------------------------------------ #
    # Input handlers
    # ------------------------------------------------------------------ #

    def _on_return_pressed(self):
        text = self.command_input.text().strip()
        if not text:
            return
        self.command_input.clear()
        self.command_entered.emit(text)

    def _on_send_clicked(self):
        self._on_return_pressed()

    def _on_mic_clicked(self):
        self.voice_listen_requested.emit()

    # ------------------------------------------------------------------ #
    # Public methods used by controller
    # ------------------------------------------------------------------ #

    def append_system_message_animated(self, text: str):
        """
        Append a system message from VORTEX.
        Styling: [VORTEX] prefix in blue, text in green.
        """
        if not text:
            return
        html = (
            f'<span style="color:{self.BLUE};">[VORTEX]</span> '
            f'<span style="color:{self.GREEN};">{self._escape(text)}</span>'
        )
        self._append_console_html(html)

    def append_user_command(self, text: str):
        """
        Append a user command line.
        Also logs into the "Commands" tab.
        """
        if not text:
            return

        html = (
            f'<span style="color:{self.BLUE};">[YOU]</span> '
            f'<span style="color:{self.GREEN};">{self._escape(text)}</span>'
        )
        self._append_console_html(html)

        self.commands_list.addItem(QListWidgetItem(text))
        self.commands_list.scrollToBottom()

    def add_timeline_entry(self, text: str):
        """
        Add an entry string to the Timeline tab.
        """
        self.timeline_list.addItem(QListWidgetItem(text))
        self.timeline_list.scrollToBottom()

    def update_memory_panel(self, text: str):
        """
        Replace the Memory tab text.
        """
        self.memory_view.setPlainText(text)

    def set_status(self, text: str):
        """
        Update the top status label.
        """
        self.status_label.setText(f"STATUS: {text}")

    def set_theme(self, theme: VortexTheme):
        """
        Public entry point to switch the visual theme.
        """
        self._apply_theme_styles(theme)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _escape(self, text: str) -> str:
        """
        Simple HTML escape for < and > to avoid breaking formatting.
        """
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def _append_console_html(self, html: str):
        """
        Append a line of HTML to the console with a newline.
        """
        cursor = self.console.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        if self.console.toPlainText():
            cursor.insertHtml("<br/>" + html)
        else:
            cursor.insertHtml(html)
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()

    def _apply_theme_styles(self, theme: VortexTheme):
        """
        Apply style sheets for the whole window depending on theme.
        Only uses the 4 allowed colors.
        """

        # Base: AMOLED black background, green foreground.
        base_style = f"""
        QMainWindow {{
            background-color: {self.BLACK};
        }}
        QWidget {{
            background-color: {self.BLACK};
            color: {self.GREEN};
            font-family: Consolas, Menlo, "Courier New", monospace;
            font-size: 11pt;
        }}
        QTabWidget::pane {{
            border: 1px solid {self.BLUE};
        }}
        QTabBar::tab {{
            background-color: {self.BLACK};
            color: {self.GREEN};
            padding: 4px 8px;
            border: 1px solid {self.BLUE};
        }}
        QTabBar::tab:selected {{
            background-color: {self.BLUE};
            color: {self.BLACK};
        }}
        QTextEdit, QLineEdit {{
            background-color: {self.BLACK};
            color: {self.GREEN};
            border: 1px solid {self.BLUE};
        }}
        QLineEdit#commandInput {{
            padding: 4px;
        }}
        QListWidget {{
            background-color: {self.BLACK};
            color: {self.GREEN};
            border: 1px solid {self.BLUE};
        }}
        QPushButton {{
            background-color: {self.BLACK};
            color: {self.GREEN};
            border: 1px solid {self.BLUE};
            padding: 4px 10px;
        }}
        QPushButton:hover {{
            background-color: {self.BLUE};
            color: {self.BLACK};
        }}
        QFrame#centerFrame {{
            border: 1px solid {self.BLUE};
        }}
        QFrame#inputFrame {{
            border-top: 1px solid {self.BLUE};
        }}
        QFrame#statusFrame {{
            border: 1px solid {self.BLUE};
        }}
        QLabel#statusLabel {{
            font-weight: bold;
        }}
        """

        # Theme-specific overrides
        if theme == VortexTheme.NORMAL:
            extra = ""
        elif theme == VortexTheme.SECURITY:
            extra = f"""
            QFrame#centerFrame {{
                border: 1px solid {self.RED};
            }}
            QFrame#statusFrame {{
                border: 1px solid {self.RED};
            }}
            QLabel#statusLabel {{
                color: {self.RED};
            }}
            """
        elif theme == VortexTheme.LOCKDOWN:
            # Lockdown: stronger red, but still same red color
            extra = f"""
            QFrame#centerFrame {{
                border: 2px solid {self.RED};
            }}
            QFrame#statusFrame {{
                border: 2px solid {self.RED};
            }}
            QLabel#statusLabel {{
                color: {self.RED};
            }}
            """
        else:
            extra = ""

        self.setStyleSheet(base_style + extra)

# vortex/ui.py

"""
PyQt6 UI for VORTEX.

Phase 1++:
- Fullscreen window
- Black + green tech theme, red on security
- Console output + recent commands + timeline tab
- Typing animation for system messages
- Simple CPU/RAM monitor in status bar
"""

from PyQt6 import QtWidgets, QtGui, QtCore
import psutil


class VortexTheme:
    NORMAL = "normal"
    SECURITY = "security"

class VortexWindow(QtWidgets.QMainWindow):
    command_entered = QtCore.pyqtSignal(str)
    voice_listen_requested = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()

        self._current_theme = VortexTheme.NORMAL

        # typing animation state
        self._msg_queue: list[str] = []
        self._animating = False
        self._current_msg = ""
        self._current_index = 0
        self._typing_timer = QtCore.QTimer(self)
        self._typing_timer.timeout.connect(self._typing_step)

        self.setWindowTitle("VORTEX - Voice-Oriented Responsive Terminal EXecutive")
        self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint)
        self.showFullScreen()

        self._setup_palette()
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_system_monitor()

    # ---------- Theme & palette ----------

    def _setup_palette(self):
        palette = self.palette()
        if self._current_theme == VortexTheme.NORMAL:
            bg = QtGui.QColor(0, 0, 0)  # AMOLED black
            text = QtGui.QColor(0, 255, 120)  # neon green
        else:
            bg = QtGui.QColor(0, 0, 0)
            text = QtGui.QColor(255, 60, 60)  # alert red

        palette.setColor(QtGui.QPalette.ColorRole.Window, bg)
        palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(10, 10, 10))
        palette.setColor(QtGui.QPalette.ColorRole.Text, text)
        palette.setColor(QtGui.QPalette.ColorRole.WindowText, text)
        self.setPalette(palette)

        accent_color = "#00FF78" if self._current_theme == VortexTheme.NORMAL else "#FF4040"

        self._console_style = (
            "QTextEdit {"
            "background-color: #050505;"
            f"color: {accent_color};"
            "font-family: 'Consolas', monospace;"
            "font-size: 14px;"
            "border: 1px solid #008040;"
            "}"
        )
        self._list_style = (
            "QListWidget {"
            "background-color: #050505;"
            f"color: {accent_color};"
            "font-family: 'Consolas', monospace;"
            "font-size: 12px;"
            "border: 1px solid #008040;"
            "}"
        )
        self._status_style = (
            f"color: {accent_color}; font-family: 'Consolas', monospace; font-size: 16px;"
        )

    def set_theme(self, theme: str):
        if theme not in (VortexTheme.NORMAL, VortexTheme.SECURITY):
            return
        self._current_theme = theme
        self._setup_palette()
        # Re-apply styles
        self.console.setStyleSheet(self._console_style)
        self.recent_commands.setStyleSheet(self._list_style)
        self.timeline_list.setStyleSheet(self._list_style)
        self.status_label.setStyleSheet(self._status_style)
        self.stats_label.setStyleSheet(self._status_style)

    # ---------- UI layout ----------

    def _setup_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)

        # Top status bar (two labels: status + system stats)
        status_layout = QtWidgets.QHBoxLayout()
        status_layout.setSpacing(20)

        self.status_label = QtWidgets.QLabel("STATUS: IDLE")
        self.status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.status_label.setStyleSheet(self._status_style)

        self.stats_label = QtWidgets.QLabel("CPU: --%  RAM: --%")
        self.stats_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.stats_label.setStyleSheet(self._status_style)

        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.stats_label)

        # Main area: console + right side tabs
        center_layout = QtWidgets.QHBoxLayout()
        center_layout.setSpacing(10)

        # Console (main output)
        self.console = QtWidgets.QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet(self._console_style)

        # Right side: tabs (Recent commands + Timeline)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabPosition(QtWidgets.QTabWidget.TabPosition.North)

        self.recent_commands = QtWidgets.QListWidget()
        self.recent_commands.setStyleSheet(self._list_style)
        self.timeline_list = QtWidgets.QListWidget()
        self.timeline_list.setStyleSheet(self._list_style)

        self.tabs.addTab(self.recent_commands, "Commands")
        self.tabs.addTab(self.timeline_list, "Timeline")
        self.tabs.setMaximumWidth(340)

        center_layout.addWidget(self.console, stretch=3)
        center_layout.addWidget(self.tabs, stretch=1)

        # Command input (bottom)
        self.command_input = QtWidgets.QLineEdit()
        self.command_input.setPlaceholderText("Type a command for VORTEX and press Enter...")
        self.command_input.setStyleSheet(
            "QLineEdit {"
            "background-color: #050505;"
            "color: #00FF78;"
            "font-family: 'Consolas', monospace;"
            "font-size: 14px;"
            "border: 1px solid #008040;"
            "padding: 6px;"
            "}"
        )
        self.command_input.returnPressed.connect(self._on_command_entered)

        main_layout.addLayout(status_layout)
        main_layout.addLayout(center_layout)
        main_layout.addWidget(self.command_input)

    def _setup_shortcuts(self):
        # ESC to exit
        quit_sc = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self)
        quit_sc.activated.connect(self.close)

        # Ctrl+Space to trigger voice listening
        listen_sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Space"), self)
        listen_sc.activated.connect(self._on_listen_shortcut)
    
    def _on_listen_shortcut(self):
        """
        Called when the user presses Ctrl+Space.
        We just emit a signal; controller will handle audio.
        """
        self.set_status("LISTENING (voice)")
        self.voice_listen_requested.emit()


    def _setup_system_monitor(self):
        """Update CPU/RAM info periodically."""
        self._stats_timer = QtCore.QTimer(self)
        self._stats_timer.timeout.connect(self._update_stats)
        self._stats_timer.start(1000)  # every second

    def _update_stats(self):
        cpu = psutil.cpu_percent(interval=0.0)
        ram = psutil.virtual_memory().percent
        self.stats_label.setText(f"CPU: {cpu:4.1f}%   RAM: {ram:4.1f}%")

    # ---------- Public helpers ----------

    @QtCore.pyqtSlot(str)
    def append_system_message(self, text: str):
        """Instant append (not animated). Keep for fallback if needed."""
        self._append_line(f"[VORTEX] {text}")

    @QtCore.pyqtSlot(str)
    def append_system_message_animated(self, text: str):
        """
        Enqueue a system message to be shown with typing animation.
        """
        self._msg_queue.append(f"[VORTEX] {text}")
        if not self._animating:
            self._start_next_message()

    @QtCore.pyqtSlot(str)
    def append_user_command(self, text: str):
        self._append_line(f"[YOU] {text}")
        self.recent_commands.addItem(text)
        self.recent_commands.scrollToBottom()

    @QtCore.pyqtSlot(str)
    def add_timeline_entry(self, text: str):
        self.timeline_list.addItem(text)
        self.timeline_list.scrollToBottom()

    def set_status(self, text: str):
        self.status_label.setText(f"STATUS: {text}")

    # ---------- Internal helpers ----------

    def _append_line(self, text: str):
        self.console.append(text)
        self.console.moveCursor(QtGui.QTextCursor.MoveOperation.End)

    def _on_command_entered(self):
        text = self.command_input.text().strip()
        if not text:
            return
        self.command_input.clear()
        self.append_user_command(text)
        self.command_entered.emit(text)

    # ---------- Typing animation ----------

    def _start_next_message(self):
        if not self._msg_queue:
            self._animating = False
            self._typing_timer.stop()
            return

        self._animating = True
        self._current_msg = self._msg_queue.pop(0)
        self._current_index = 0

        # Add a new empty line first
        self.console.append("")
        self.console.moveCursor(QtGui.QTextCursor.MoveOperation.End)
        self._typing_timer.start(15)  # ms between characters

    def _typing_step(self):
        if self._current_index >= len(self._current_msg):
            # Done with this message
            self._typing_timer.stop()
            self._start_next_message()
            return

        cursor = self.console.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        cursor.insertText(self._current_msg[self._current_index])
        self.console.setTextCursor(cursor)
        self._current_index += 1

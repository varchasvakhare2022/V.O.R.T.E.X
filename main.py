# main.py

from __future__ import annotations

import sys
from PyQt6 import QtWidgets

from vortex.ui import VortexWindow
from vortex.controller import VortexController


def main():
    app = QtWidgets.QApplication(sys.argv)

    window = VortexWindow()
    controller = VortexController(window)

    # Jarvis-style: start full screen / maximized
    window.showFullScreen()   # use showFullScreen() if you want *true* full-screen

    # Make sure controller isn't garbage-collected
    window.controller = controller  # type: ignore

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

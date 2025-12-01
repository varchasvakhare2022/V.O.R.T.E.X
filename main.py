# main.py

import sys
from PyQt6 import QtWidgets

from vortex.ui import VortexWindow
from vortex.controller import VortexController


def main():
    app = QtWidgets.QApplication(sys.argv)

    window = VortexWindow()
    controller = VortexController(window, owner_name="Varchasva")

    window.show()
    exit_code = app.exec()

    controller.shutdown()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

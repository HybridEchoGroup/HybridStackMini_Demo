"""HybridStackMini Demo

Run this file with uv run main.py
from the main directory to start the program.
"""

import sys

from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("HybridStackMini Demo")
    app.setOrganizationName("HybridEcho")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

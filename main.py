"""HybridStackMini Demo

Entry point for the application.
"""

import sys

from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow


def main() -> None:
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("HybridStackMini Demo")
    app.setOrganizationName("HybridEcho")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

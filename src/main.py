"""HybridStackMini Demo

Run this file with uv run main.py
from the main directory to start the program.
"""

import logging
import sys

from PyQt6.QtWidgets import QApplication

import config
import log as log
from gui.main_window import MainWindow


def main() -> None:
    log.setup(level=logging.DEBUG, log_file="../logs/pico.log")
    _log = logging.getLogger(__name__)
    _log.info("Application started")
    config.log_config()
    app = QApplication(sys.argv)
    app.setApplicationName("HybridStackMini Demo")
    app.setOrganizationName("HybridEcho")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

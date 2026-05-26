"""Central logging configuration for the HybridStackMini demo.

Call log.setup() once at application startup (before creating QApplication).
Every module then gets its own logger with:

    import logging
    _log = logging.getLogger(__name__)

Loggers whose name starts with "driver" are tagged [DRIVER].
All other loggers are tagged with their standard level: [INFO], [WARNING], etc.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


class _TagFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.tag = "DRIVER" if record.name.startswith("driver") else record.levelname
        return super().format(record)


class _NoDriverFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not record.name.startswith("driver")


_FMT      = "%(asctime)s [%(tag)s] %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup(level: int = logging.DEBUG, log_file: str | None = "app.log") -> None:
    """Configure the root logger.  Call once before QApplication is created.

    Parameters
    ----------
    level    : minimum log level (default DEBUG — shows everything)
    log_file : path for the rotating log file, or None to disable file logging
    """
    fmt = _TagFormatter(_FMT, datefmt=_DATE_FMT)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    console.addFilter(_NoDriverFilter())   # driver logs go to file only

    handlers: list[logging.Handler] = [console]

    if log_file:
        p = Path(log_file)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        stamped = p.with_stem(f"{p.stem}_{ts}")
        stamped.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(stamped, encoding="utf-8")
        fh.setFormatter(fmt)
        handlers.append(fh)                # file gets everything

    logging.basicConfig(level=level, handlers=handlers, force=True)

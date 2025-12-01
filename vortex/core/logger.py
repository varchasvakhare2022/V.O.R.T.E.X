# vortex/core/logger.py

"""
Logging helper for VORTEX.

Phase 1:
- Logs to file and console
- Used by controller, command engine, etc.
"""

import logging
from pathlib import Path


def setup_logging(log_dir: Path | None = None) -> logging.Logger:
    if log_dir is None:
        log_dir = Path(__file__).resolve().parents[2] / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "vortex.log"

    logger = logging.getLogger("vortex")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if called twice
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    fh.setLevel(logging.INFO)
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch.setLevel(logging.INFO)
    logger.addHandler(ch)

    logger.info("VORTEX logging initialized.")
    return logger

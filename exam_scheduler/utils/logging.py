"""File and console logging setup."""

import logging
from pathlib import Path


def setup_logging() -> logging.Logger:
    log_path = Path("logs") / "app.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("exam_scheduler")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)
    return logger

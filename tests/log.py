import logging
import os
from pathlib import Path

from typeguard import typechecked

from spatialoperations.logging import logger


def setup_logger():
    logger = logging.getLogger("spatialoperations._logger")
    logger.setLevel(logging.INFO)
    log_dir = Path("tests/logs")
    log_dir.mkdir(exist_ok=True, parents=True)
    log_file = log_dir / "log.log"
    if log_file.exists():
        try:
            os.remove(log_file)
        except Exception as e:
            print(f"Error removing log file: {e}")
    file_handler = logging.FileHandler(log_file, mode="w")
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


logger = setup_logger()

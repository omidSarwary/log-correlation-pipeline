"""Phase 2 logging framework for the pipeline.

This module configures the shared application logger so messages are written to
both the console and the repository log file at ``logs/system.log``.

The actual correlation logic is intentionally deferred to a later phase; for
now, this module focuses on creating a reusable and testable logging foundation.
"""

from __future__ import annotations

import logging
from pathlib import Path


# The repository keeps runtime logs in the shared logs directory.
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "system.log"

# A dedicated logger name keeps this configuration isolated from other modules.
LOGGER_NAME = "multi_platform_log_correlation_pipeline"


def _build_logger() -> logging.Logger:
    """Create or return the shared logger used by the project.

    The logger is configured exactly once so repeated calls do not duplicate
    handlers or emit the same message multiple times.
    """

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)

    # When the module is imported more than once, keep the existing handlers.
    if logger.handlers:
        return logger

    # Ensure the log directory exists before the file handler tries to write.
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Match the required timestamp | level | message format.
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console output gives immediate feedback during local runs and CI.
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # File output persists the same messages for later investigation.
    file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger


def log_info(message: str) -> None:
    """Write an informational message to the shared log outputs."""

    _build_logger().info(message)


def log_warning(message: str) -> None:
    """Write a warning message to the shared log outputs."""

    _build_logger().warning(message)


def log_error(message: str) -> None:
    """Write an error message to the shared log outputs."""

    _build_logger().error(message)


def main() -> None:
    """Emit a small demo sequence so the logging path can be verified easily."""

    log_info("Phase 2 logging framework initialized.")
    log_warning("Phase 2 warning example written to console and file.")
    log_error("Phase 2 error example written to console and file.")


if __name__ == "__main__":
    main()

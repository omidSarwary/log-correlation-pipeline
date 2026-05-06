"""Phase 5 fallback system and data seeder for the pipeline.

This module keeps the logging foundation from Phase 2 and adds the fallback
layer required for Phase 5. The new logic does two things:

1. Detects when collector output is missing or empty and loads data from the
   repository's ``data`` directory instead of failing.
2. Seeds realistic Linux and Windows test data only when the data directory is
   completely empty, so later phases have predictable sample input.

The actual correlation engine is intentionally deferred to a later phase.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


# The repository keeps runtime logs in the shared logs directory.
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "system.log"

# The data directory stores both collector output and seeded fallback files.
DATA_DIR = BASE_DIR / "data"
LINUX_DATA_FILE = DATA_DIR / "linux_data.json"
WINDOWS_DATA_FILE = DATA_DIR / "windows_data.csv"

# A dedicated logger name keeps this configuration isolated from other modules.
LOGGER_NAME = "multi_platform_log_correlation_pipeline"


@dataclass(frozen=True)
class SeedRecord:
    """Describe one fallback record that should be emitted into the seed data."""

    timestamp: str
    username: str
    ip: str


def _build_logger() -> logging.Logger:
    """Create or return the shared logger used by the project."""

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


def _ensure_data_directory() -> None:
    """Create the data directory before any read or write operation."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _is_empty_file(path: Path) -> bool:
    """Return True when a file does not exist or contains no usable data."""

    if not path.exists():
        return True

    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return True
        return not bool(payload)

    if path.suffix.lower() == ".csv":
        try:
            with path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
        except OSError:
            return True
        return not bool(rows)

    try:
        return path.stat().st_size == 0
    except OSError:
        return True


def _data_folder_is_empty() -> bool:
    """Check whether the repository data folder has any reusable content."""

    if not DATA_DIR.exists():
        return True

    meaningful_entries = [
        entry
        for entry in DATA_DIR.iterdir()
        if entry.name not in {".gitkeep"} and entry.is_file() and entry.stat().st_size > 0
    ]
    return not meaningful_entries


def _seed_linux_records() -> list[SeedRecord]:
    """Return realistic Linux failed-login records for testing fallback logic."""

    return [
        SeedRecord("May  6 08:11:01", "root", "203.0.113.10"),
        SeedRecord("May  6 08:11:12", "root", "203.0.113.10"),
        SeedRecord("May  6 08:11:23", "root", "203.0.113.10"),
        SeedRecord("May  6 08:11:34", "root", "203.0.113.10"),
        SeedRecord("May  6 08:11:45", "root", "203.0.113.10"),
        SeedRecord("May  6 12:45:03", "alice", "198.51.100.42"),
        SeedRecord("May  6 18:03:21", "svc-backup", "192.0.2.77"),
        SeedRecord("May  6 22:17:08", "jdoe", "198.51.100.18"),
    ]


def _seed_windows_records() -> list[dict[str, str]]:
    """Return realistic Windows failed-logon records for testing fallback logic."""

    return [
        {"TargetUserName": "root", "IpAddress": "203.0.113.10", "TimeCreated": "2026-05-06T08:11:01"},
        {"TargetUserName": "root", "IpAddress": "203.0.113.10", "TimeCreated": "2026-05-06T08:11:12"},
        {"TargetUserName": "alice", "IpAddress": "198.51.100.42", "TimeCreated": "2026-05-06T12:45:03"},
        {"TargetUserName": "svc-backup", "IpAddress": "192.0.2.77", "TimeCreated": "2026-05-06T18:03:21"},
        {"TargetUserName": "jdoe", "IpAddress": "198.51.100.18", "TimeCreated": "2026-05-06T22:17:08"},
    ]


def seed_data_if_needed() -> bool:
    """Seed realistic Linux and Windows test data when the folder is empty.

    Returns True when seeding happened so callers can report the fallback path.
    """

    _ensure_data_directory()

    if not _data_folder_is_empty():
        return False

    log_warning("Data folder is empty, creating fallback seed data for testing.")

    linux_seed = [
        {
            "timestamp": record.timestamp,
            "username": record.username,
            "ip": record.ip,
        }
        for record in _seed_linux_records()
    ]
    windows_seed = _seed_windows_records()

    LINUX_DATA_FILE.write_text(
        json.dumps(linux_seed, indent=2),
        encoding="utf-8",
    )

    with WINDOWS_DATA_FILE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["TargetUserName", "IpAddress", "TimeCreated"])
        writer.writeheader()
        writer.writerows(windows_seed)

    log_info("Seeded fallback Linux JSON and Windows CSV data into the data folder.")
    return True


def load_linux_data() -> list[dict[str, str]]:
    """Load Linux collector data, falling back to seeded data when required."""

    if _is_empty_file(LINUX_DATA_FILE):
        log_warning("Linux collector output is missing or empty, using fallback data.")
        seed_data_if_needed()

    if _is_empty_file(LINUX_DATA_FILE):
        log_error("Unable to load Linux data because no usable dataset is available.")
        return []

    try:
        return json.loads(LINUX_DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log_error(f"Failed to load Linux JSON data: {exc}")
        return []


def load_windows_data() -> list[dict[str, str]]:
    """Load Windows collector data, falling back to seeded data when required."""

    if _is_empty_file(WINDOWS_DATA_FILE):
        log_warning("Windows collector output is missing or empty, using fallback data.")
        seed_data_if_needed()

    if _is_empty_file(WINDOWS_DATA_FILE):
        log_error("Unable to load Windows data because no usable dataset is available.")
        return []

    try:
        with WINDOWS_DATA_FILE.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as exc:
        log_error(f"Failed to load Windows CSV data: {exc}")
        return []


def load_available_data() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Load both data sources while recovering automatically from empty output."""

    linux_data = load_linux_data()
    windows_data = load_windows_data()
    return linux_data, windows_data


def main() -> None:
    """Run the Phase 5 fallback path and print a short status summary."""

    log_info("Phase 5 fallback system initialized.")
    seed_created = seed_data_if_needed()
    linux_data, windows_data = load_available_data()

    if seed_created:
        log_info("Fallback seeding completed successfully.")
    else:
        log_info("Fallback seeding was not required because reusable data already existed.")

    # Keep the main entry point lightweight so future phases can build on it.
    print(f"Linux records loaded: {len(linux_data)}")
    print(f"Windows records loaded: {len(windows_data)}")


if __name__ == "__main__":
    main()

"""Runtime orchestration, fallback loading, correlation, and reporting.

The pipeline attempts to collect system logs first. If those logs are not
available, the existing files in ``data/`` are used as fallback input. When
neither source contains usable logs, the program exits cleanly after logging a
single clear error message.
"""

from __future__ import annotations

from collections import defaultdict
import csv
import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
import shutil


# The repository keeps runtime logs in the shared logs directory.
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "system.log"

# The data directory stores collector output and fallback input files.
DATA_DIR = BASE_DIR / "data"
LINUX_DATA_FILE = DATA_DIR / "linux_data.json"
WINDOWS_DATA_FILE = DATA_DIR / "windows_data.csv"
KNOWN_MACHINES_FILE = BASE_DIR / "known_machines.csv"
OUTPUT_REPORT_FILE = BASE_DIR / "output" / "final_security_report.txt"

# A dedicated logger name keeps this configuration isolated from other modules.
LOGGER_NAME = "multi_platform_log_correlation_pipeline"


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


def load_linux_data() -> list[dict[str, str]]:
    """Load Linux collector data from the existing JSON file, if present."""

    if not LINUX_DATA_FILE.exists() or _is_empty_file(LINUX_DATA_FILE):
        return []

    try:
        payload = json.loads(LINUX_DATA_FILE.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
        log_error(f"Linux data file has unexpected structure: {LINUX_DATA_FILE}")
        return []
    except (OSError, json.JSONDecodeError) as exc:
        log_error(f"Failed to load Linux JSON data: {exc}")
        return []


def load_windows_data() -> list[dict[str, str]]:
    """Load Windows collector data from the existing CSV file, if present."""

    if not WINDOWS_DATA_FILE.exists() or _is_empty_file(WINDOWS_DATA_FILE):
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


def load_known_machines() -> dict[str, str]:
    """Load the baseline machine list into a fast IP-to-machine dictionary."""

    if not KNOWN_MACHINES_FILE.exists():
        log_error(f"Baseline file missing: {KNOWN_MACHINES_FILE}")
        return {}

    machines: dict[str, str] = {}
    try:
        with KNOWN_MACHINES_FILE.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                ip_address = (row.get("IpAddress") or "").strip()
                machine_name = (row.get("MachineName") or "").strip()
                if ip_address:
                    machines[ip_address] = machine_name or "unknown-machine"
    except OSError as exc:
        log_error(f"Failed to load known_machines.csv: {exc}")
        return {}

    log_info(f"Loaded {len(machines)} known machine records from baseline CSV.")
    return machines


def _parse_linux_timestamp(timestamp_text: str) -> datetime:
    """Convert a Linux auth.log timestamp into a datetime object."""

    # Linux auth logs do not store a year, so we anchor parsing to the current year.
    return datetime.strptime(f"{datetime.now().year} {timestamp_text}", "%Y %b %d %H:%M:%S")


def _parse_windows_timestamp(timestamp_text: str) -> datetime:
    """Convert a Windows ISO timestamp into a datetime object."""

    return datetime.fromisoformat(timestamp_text)


def _is_off_hours(event_time: datetime) -> bool:
    """Return True when a login occurs outside the standard workday."""

    # The project definition treats logins before 09:00 and at or after 17:00 as off-hours.
    return event_time.hour < 9 or event_time.hour >= 17


def _normalize_linux_event(event: dict[str, str]) -> dict[str, str]:
    """Normalize a Linux event into a common correlation structure."""

    return {
        "source": "linux",
        "ip": (event.get("ip") or "").strip(),
        "username": (event.get("username") or "").strip(),
        "timestamp": (event.get("timestamp") or "").strip(),
    }


def _normalize_windows_event(event: dict[str, str]) -> dict[str, str]:
    """Normalize a Windows event into a common correlation structure."""

    return {
        "source": "windows",
        "ip": (event.get("IpAddress") or "").strip(),
        "username": (event.get("TargetUserName") or "").strip(),
        "timestamp": (event.get("TimeCreated") or "").strip(),
    }


def _build_event_stream(
    linux_data: list[dict[str, str]],
    windows_data: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Combine Linux and Windows records into one correlation-friendly stream."""

    normalized_events = [_normalize_linux_event(event) for event in linux_data]
    normalized_events.extend(_normalize_windows_event(event) for event in windows_data)
    return normalized_events


def correlate_events(
    known_machines: dict[str, str],
    linux_data: list[dict[str, str]],
    windows_data: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Apply the correlation rules to the combined event stream."""

    events = _build_event_stream(linux_data, windows_data)
    failed_attempts_by_ip: dict[str, int] = defaultdict(int)
    first_event_by_ip: dict[str, dict[str, str]] = {}
    findings: list[dict[str, str]] = []
    recorded_high_ips: set[str] = set()
    recorded_unknown_ips: set[str] = set()

    for event in events:
        ip_address = event["ip"]
        if not ip_address:
            continue

        # Track how many failures we have seen per source IP for brute-force detection.
        failed_attempts_by_ip[ip_address] += 1

        # Keep the first event so we can attach a stable timestamp to IP-level findings.
        first_event_by_ip.setdefault(ip_address, event)

        # Rule 1: flag any IP that is not part of the trusted baseline.
        if ip_address not in known_machines and ip_address not in recorded_unknown_ips:
            recorded_unknown_ips.add(ip_address)
            findings.append(
                {
                    "severity": "CRITICAL",
                    "rule": "Unknown IP",
                    "ip": ip_address,
                    "username": event["username"],
                    "timestamp": event["timestamp"],
                    "source": event["source"],
                    "detail": "IP address is not listed in known_machines.csv.",
                }
            )
            log_error(
                f"CRITICAL Unknown IP detected: {ip_address} "
                f"({event['source']} user={event['username']} time={event['timestamp']})"
            )

        # Rule 3: flag logins that occur outside normal business hours.
        timestamp_text = event["timestamp"]
        try:
            event_time = (
                _parse_linux_timestamp(timestamp_text)
                if event["source"] == "linux"
                else _parse_windows_timestamp(timestamp_text)
            )
        except ValueError:
            log_warning(f"Unable to parse timestamp for off-hours detection: {timestamp_text}")
            continue

        if _is_off_hours(event_time):
            findings.append(
                {
                    "severity": "MEDIUM",
                    "rule": "Off-hours login",
                    "ip": ip_address,
                    "username": event["username"],
                    "timestamp": timestamp_text,
                    "source": event["source"],
                    "detail": "Login attempt occurred outside standard office hours.",
                }
            )
            log_warning(
                f"MEDIUM Off-hours login detected: {ip_address} "
                f"({event['source']} user={event['username']} time={timestamp_text})"
            )

    # Rule 2: once all events are counted, flag IPs that cross the brute-force threshold.
    for ip_address, attempt_count in failed_attempts_by_ip.items():
        if attempt_count >= 5 and ip_address not in recorded_high_ips:
            recorded_high_ips.add(ip_address)
            reference_event = first_event_by_ip[ip_address]
            findings.append(
                {
                    "severity": "HIGH",
                    "rule": "Brute force",
                    "ip": ip_address,
                    "username": reference_event["username"],
                    "timestamp": reference_event["timestamp"],
                    "source": reference_event["source"],
                    "detail": f"{attempt_count} failed attempts detected for the same IP.",
                }
            )
            log_warning(
                f"HIGH Brute-force threshold reached for {ip_address} with {attempt_count} failed attempts."
            )

    severity_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    findings.sort(
        key=lambda item: (
            severity_rank.get(item["severity"], 99),
            item["timestamp"],
            item["ip"],
            item["rule"],
        )
    )
    return findings


def _summarize_findings(findings: list[dict[str, str]]) -> dict[str, int]:
    """Build a simple severity summary for the correlation results."""

    summary = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0}
    for finding in findings:
        severity = finding["severity"]
        if severity in summary:
            summary[severity] += 1
    return summary


def _build_report_lines(
    findings: list[dict[str, str]],
    summary: dict[str, int],
    linux_count: int,
    windows_count: int,
    known_machine_count: int,
) -> list[str]:
    """Assemble a readable report body from the current analysis results."""

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = [
        "Multi-Platform Log Correlation Pipeline",
        "Final Security Report",
        "=" * 72,
        f"Generated at: {generated_at}",
        "",
        "Summary",
        "-" * 72,
        f"Linux records processed: {linux_count}",
        f"Windows records processed: {windows_count}",
        f"Known machines loaded: {known_machine_count}",
        f"Total findings: {len(findings)}",
        f"CRITICAL findings: {summary['CRITICAL']}",
        f"HIGH findings: {summary['HIGH']}",
        f"MEDIUM findings: {summary['MEDIUM']}",
        "",
        "Categorized Risks",
        "-" * 72,
    ]

    severity_labels = ["CRITICAL", "HIGH", "MEDIUM"]
    for severity in severity_labels:
        severity_findings = [finding for finding in findings if finding["severity"] == severity]
        lines.append(f"{severity} ({len(severity_findings)})")
        if not severity_findings:
            lines.append("  - None detected")
        else:
            for finding in severity_findings:
                lines.append(
                    "  - "
                    f"{finding['timestamp']} | "
                    f"{finding['ip']} | "
                    f"{finding['username']} | "
                    f"{finding['rule']} | "
                    f"{finding['detail']}"
                )
        lines.append("")

    lines.extend(
        [
            "Event Timeline",
            "-" * 72,
        ]
    )

    if findings:
        for finding in findings:
            lines.append(
                f"{finding['timestamp']} | {finding['severity']} | "
                f"{finding['ip']} | {finding['username']} | {finding['source']} | "
                f"{finding['rule']}"
            )
    else:
        lines.append("No findings were generated.")

    lines.extend(
        [
            "",
            "Notes",
            "-" * 72,
            "This report was generated automatically from the current correlation results.",
            "Timestamps are preserved from the collector data to support investigation.",
            "",
        ]
    )

    return lines


def generate_final_security_report(
    findings: list[dict[str, str]],
    summary: dict[str, int],
    linux_count: int,
    windows_count: int,
    known_machine_count: int,
) -> Path:
    """Write the final report to disk in a readable, structured format."""

    OUTPUT_REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    report_lines = _build_report_lines(
        findings=findings,
        summary=summary,
        linux_count=linux_count,
        windows_count=windows_count,
        known_machine_count=known_machine_count,
    )
    OUTPUT_REPORT_FILE.write_text("\n".join(report_lines), encoding="utf-8")
    log_info(f"Final security report written to {OUTPUT_REPORT_FILE}")
    return OUTPUT_REPORT_FILE


def _resolve_shell(executable_names: list[str]) -> str | None:
    """Return the first available shell or command executable from a candidate list."""

    for candidate in executable_names:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _run_collector(command: list[str], collector_name: str) -> bool:
    """Run a collector subprocess and report success or failure safely."""

    log_info(f"Starting {collector_name} collector.")

    try:
        completed = subprocess.run(
            command,
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            check=False,
            env=os.environ.copy(),
        )
    except FileNotFoundError as exc:
        error_message = f"{collector_name} collector could not start: {exc}"
        print(error_message)
        log_error(error_message)
        return False
    except OSError as exc:
        error_message = f"{collector_name} collector failed to launch: {exc}"
        print(error_message)
        log_error(error_message)
        return False

    # Forward any collector output so runtime diagnostics remain visible.
    stdout_text = (completed.stdout or "").strip()
    stderr_text = (completed.stderr or "").strip()
    if stdout_text:
        for line in stdout_text.splitlines():
            log_info(f"{collector_name} stdout: {line}")
    if stderr_text:
        for line in stderr_text.splitlines():
            log_warning(f"{collector_name} stderr: {line}")

    if completed.returncode != 0:
        error_message = (
            f"{collector_name} collector exited with status {completed.returncode}. "
            "Fallback data will be used."
        )
        print(error_message)
        log_error(error_message)
        return False

    log_info(f"{collector_name} collector completed successfully.")
    return True


def _collectors_produced_data() -> bool:
    """Check whether the collector output files are present and usable."""

    return not _is_empty_file(LINUX_DATA_FILE) and not _is_empty_file(WINDOWS_DATA_FILE)


def orchestrate_collection() -> tuple[bool, bool]:
    """Run both collectors and fall back to the data directory when needed."""

    log_info("Starting collector orchestration.")

    linux_shell = _resolve_shell(["bash"])
    windows_shell = _resolve_shell(["powershell", "pwsh"])

    linux_success = False
    windows_success = False

    if linux_shell:
        linux_success = _run_collector([linux_shell, "scripts/linux_collector.sh"], "Linux")
    else:
        print("Linux collector could not start because bash is unavailable.")
        log_error("Linux collector could not start because bash is unavailable.")

    if windows_shell:
        windows_success = _run_collector(
            [windows_shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/windows_collector.ps1"],
            "Windows",
        )
    else:
        print("Windows collector could not start because PowerShell is unavailable.")
        log_error("Windows collector could not start because PowerShell is unavailable.")

    if not linux_success or not windows_success:
        log_warning("One or more collectors failed, checking data/ for fallback input.")

    return linux_success and windows_success, _collectors_produced_data()


def main() -> int:
    """Run collection, fallback loading, correlation, and report generation."""

    log_info("Orchestrator initialized.")
    orchestrated_success, collectors_produced_data = orchestrate_collection()
    linux_data, windows_data = load_available_data()

    if not linux_data and not windows_data:
        log_error("No log files found in system or data folder")
        return 1

    if not orchestrated_success:
        log_warning("System collectors were incomplete; using available data files from data/.")
    elif not collectors_produced_data:
        log_warning("System collectors did not produce usable output; using data/ fallback input.")

    # Emit a compact, readable summary so manual testing can confirm every rule.
    print(f"Linux records loaded: {len(linux_data)}")
    print(f"Windows records loaded: {len(windows_data)}")

    known_machines = load_known_machines()
    findings = correlate_events(known_machines, linux_data, windows_data)
    summary = _summarize_findings(findings)

    print(f"Known machines loaded: {len(known_machines)}")
    print(f"Findings total: {len(findings)}")
    print(
        "Severity counts: "
        f"CRITICAL={summary['CRITICAL']} "
        f"HIGH={summary['HIGH']} "
        f"MEDIUM={summary['MEDIUM']}"
    )

    report_path = generate_final_security_report(
        findings=findings,
        summary=summary,
        linux_count=len(linux_data),
        windows_count=len(windows_data),
        known_machine_count=len(known_machines),
    )
    print(f"Report written to: {report_path}")

    for finding in findings:
        print(
            f"{finding['severity']} | {finding['rule']} | "
            f"{finding['ip']} | {finding['timestamp']} | {finding['username']}"
        )
        log_info(
            f"{finding['severity']} finding recorded for {finding['ip']} "
            f"via {finding['rule']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env bash

# Phase 2 logging helpers for the Linux side of the pipeline.
# The actual log collection logic is intentionally deferred to later phases.

set -euo pipefail

# Resolve the repository root so the script writes to the shared log file.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${REPO_ROOT}/logs"
LOG_FILE="${LOG_DIR}/system.log"

# Create the log directory if it does not already exist.
mkdir -p "${LOG_DIR}"

# Write a standardized log line to the shared file.
log_message() {
    local level="$1"
    shift

    # Preserve the full message even when it contains spaces or punctuation.
    local message="$*"
    printf '%s | %s | %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "${level}" "${message}" >> "${LOG_FILE}"
}

# Convenience wrapper for informational messages.
log_info() {
    log_message "INFO" "$@"
}

# Convenience wrapper for warnings.
log_warning() {
    log_message "WARNING" "$@"
}

# Convenience wrapper for errors.
log_error() {
    log_message "ERROR" "$@"
}

# Phase 2 verification hook: emit a sample log line when run directly.
log_info "Linux logging helper initialized."


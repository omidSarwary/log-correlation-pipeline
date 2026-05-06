#!/usr/bin/env bash

# Phase 3 Linux collector.
# This script reads the Linux authentication log, extracts failed password
# attempts, and exports the results as structured JSON for the Python engine.

set -euo pipefail

# Allow tests to point the script at a fixture file while defaulting to the
# real system log path required by the project specification.
AUTH_LOG_PATH="${AUTH_LOG_PATH:-/var/log/auth.log}"

# Resolve repository-local paths so all outputs stay inside the project tree.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${REPO_ROOT}/logs"
LOG_FILE="${LOG_DIR}/system.log"
DATA_DIR="${REPO_ROOT}/data"
OUTPUT_FILE="${DATA_DIR}/linux_data.json"

# Ensure the destination directories exist before any writes occur.
mkdir -p "${LOG_DIR}" "${DATA_DIR}"

# Write one timestamped message to the shared log file and the console.
log_message() {
    local level="$1"
    shift

    # Join the remaining arguments into the full log message.
    local message="$*"
    local line
    line="$(printf '%s | %s | %s' "$(date '+%Y-%m-%d %H:%M:%S')" "${level}" "${message}")"

    # Console output gives immediate feedback during local runs and CI.
    printf '%s\n' "${line}"

    # Append to the shared log file so later phases can correlate events.
    printf '%s\n' "${line}" >> "${LOG_FILE}"
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

# Exit with a logged error when the input file cannot be read.
validate_input_file() {
    if [[ ! -e "${AUTH_LOG_PATH}" ]]; then
        log_error "auth.log not found at ${AUTH_LOG_PATH}"
        exit 1
    fi

    if [[ ! -r "${AUTH_LOG_PATH}" ]]; then
        log_error "Permission denied reading ${AUTH_LOG_PATH}"
        exit 1
    fi
}

# Escape JSON special characters so collected values remain valid JSON strings.
json_escape() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    value="${value//$'\t'/\\t}"
    value="${value//$'\r'/\\r}"
    value="${value//$'\n'/\\n}"
    printf '%s' "${value}"
}

# Parse one auth.log line into timestamp, username, and IP fields.
extract_failed_password_fields() {
    local line="$1"

    # Match the common sshd failed-password format used by auth.log.
    # Examples:
    #   Failed password for root from 10.0.0.1 ...
    #   Failed password for invalid user admin from 10.0.0.2 ...
    if [[ "${line}" =~ ^([A-Z][a-z]{2}[[:space:]]+[0-9]{1,2}[[:space:]]+[0-9]{2}:[0-9]{2}:[0-9]{2}).*Failed[[:space:]]password[[:space:]]for[[:space:]](invalid[[:space:]]user[[:space:]]+)?([^[:space:]]+)[[:space:]]from[[:space:]]([^[:space:]]+) ]]; then
        LOG_TIMESTAMP="${BASH_REMATCH[1]}"
        LOG_USERNAME="${BASH_REMATCH[3]}"
        LOG_IP="${BASH_REMATCH[4]}"
        return 0
    fi

    return 1
}

# Process the log file line by line and collect all failed password attempts.
collect_failed_logins() {
    local line
    local -a entries=()

    while IFS= read -r line || [[ -n "${line}" ]]; do
        # Focus only on the authentication failures required by this phase.
        if [[ "${line}" != *"Failed password"* ]]; then
            continue
        fi

        if extract_failed_password_fields "${line}"; then
            # Preserve the original timestamp, account, and source IP for later analysis.
            entries+=("{\"timestamp\":\"$(json_escape "${LOG_TIMESTAMP}")\",\"username\":\"$(json_escape "${LOG_USERNAME}")\",\"ip\":\"$(json_escape "${LOG_IP}")\"}")

            # Warn when the failure targets root because that is a high-value account.
            if [[ "${LOG_USERNAME}" == "root" ]]; then
                log_warning "Root login failure detected from ${LOG_IP} at ${LOG_TIMESTAMP}"
            fi
        fi
    done < "${AUTH_LOG_PATH}"

    # Write an empty array when no matching records are found.
    {
        printf '[\n'
        local index
        for index in "${!entries[@]}"; do
            printf '  %s' "${entries[index]}"
            if [[ "${index}" -lt $((${#entries[@]} - 1)) ]]; then
                printf ','
            fi
            printf '\n'
        done
        printf ']\n'
    } > "${OUTPUT_FILE}"
}

# Validate the source log before attempting to parse it.
validate_input_file

# Record the start of a successful collection run.
log_info "Starting Linux collector against ${AUTH_LOG_PATH}"

# Perform the extraction and export step.
collect_failed_logins

# Confirm the export completed so the run is visible in the shared log.
log_info "Linux collector wrote JSON output to ${OUTPUT_FILE}"


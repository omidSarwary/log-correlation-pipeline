# Multi-Platform Log Correlation Pipeline

Multi-Platform Log Correlation Pipeline is a phased security automation project that collects Linux and Windows authentication data, applies correlation rules, and generates a structured security report.

The repository is intentionally organized to match the phased development plan in `phasedplan.md`. Each phase adds one layer of capability without skipping ahead.

## Project Overview

The goal of the project is to reduce manual log review by automatically:

- Collecting Linux failed login data from `/var/log/auth.log`
- Collecting Windows failed logon data from Security Event ID `4625`
- Falling back to seeded sample data when live collection is not possible
- Correlating events against a baseline of known machines
- Classifying risks as `CRITICAL`, `HIGH`, or `MEDIUM`
- Writing a readable report to `output/final_security_report.txt`

The current codebase contains the collector scripts, the Python fallback/orchestration/correlation layer, and the final report generator.

## Architecture

The pipeline is split into three main layers:

- Linux collector: `scripts/linux_collector.sh`
- Windows collector: `scripts/windows_collector.ps1`
- Python control plane: `scripts/analyzer.py`

Supporting files and folders:

- Baseline machines: `known_machines.csv`
- Runtime data: `data/`
- Runtime logs: `logs/system.log`
- Final report: `output/final_security_report.txt`
- GitHub Actions workflow: `.github/workflows/verify-scripts.yml`

How the parts connect:

- The Linux collector reads failed password attempts from `auth.log` and writes JSON to `data/linux_data.json`
- The Windows collector reads Event ID `4625` entries and writes CSV to `data/windows_data.csv`
- The Python script orchestrates both collectors, enables fallback seeding when required, loads the baseline list, applies correlation rules, and generates the report

## Setup Instructions

### Requirements

- Python 3.x
- Bash
- PowerShell
- Git

### Local setup

1. Clone the repository.
2. Open the project root.
3. Make sure the following directories exist:
   - `data/`
   - `logs/`
   - `output/`
   - `scripts/`
4. Make sure the scripts are executable in your environment.

### Optional validation commands

```powershell
python -m py_compile .\scripts\analyzer.py
bash -n scripts/linux_collector.sh
```

## Execution Flow

The expected runtime flow is:

1. `scripts/analyzer.py` starts the orchestrator.
2. The orchestrator attempts to run the Linux collector.
3. The orchestrator attempts to run the Windows collector.
4. If either collector fails or produces no usable output, the fallback layer seeds or reuses data from `data/`.
5. The Python correlation engine loads:
   - `known_machines.csv`
   - `data/linux_data.json`
   - `data/windows_data.csv`
6. The report generator writes `output/final_security_report.txt`.

## Fallback Logic

Fallback is designed to keep the pipeline usable even when live collector data is unavailable.

- If the collectors fail, the orchestrator logs the failure and continues safely
- If `data/` is empty, the seeder creates realistic Linux-style JSON and Windows-style CSV data
- If collector output is missing or empty, the Python loader falls back to the seeded data
- The seeded scenarios include:
  - brute force activity
  - lateral movement-style activity
  - normal activity

This approach lets the rest of the pipeline keep working without crashing on missing logs or unavailable system sources.

## Correlation Rules

The Python analysis engine applies the following rules:

- `Unknown IP -> CRITICAL`
- `>= 5 failed attempts -> HIGH`
- `Off-hours login -> MEDIUM`

The baseline for trusted systems comes from `known_machines.csv`, which is loaded into a dictionary for fast lookups.

## CI/CD Workflow

The project includes a GitHub Actions workflow at `.github/workflows/verify-scripts.yml`.

What the workflow checks:

- Ubuntu runner
- Python setup
- `shellcheck` on `scripts/linux_collector.sh`
- Python syntax validation with `python -m py_compile scripts/analyzer.py`
- Required file and folder validation

Why this matters:

- CI catches syntax and structure problems early
- The workflow ensures the repository keeps the expected project layout
- The project follows the phase plan before moving on to later delivery work

## How to Run

Run the Python entry point from the project root:

```powershell
python .\scripts\analyzer.py
```

Expected behavior:

- Collector start and failure messages appear in the console when live collection is unavailable
- Fallback data is seeded or reused if needed
- Correlation findings are printed to the console
- A final report is written to `output/final_security_report.txt`

## How to Test

Follow these checks to verify the current system:

1. Delete `data/linux_data.json` and `data/windows_data.csv` if they exist.
2. Run `python .\scripts\analyzer.py`.
3. Confirm the console shows collector attempts, fallback usage, and correlation output.
4. Confirm `data/linux_data.json` and `data/windows_data.csv` are regenerated when the folder is empty.
5. Confirm `output/final_security_report.txt` is written.
6. Open the report and verify it contains:
   - a timestamped header
   - a summary
   - categorized risks
   - an event timeline

## Example Outputs

The report should contain sections similar to:

- `Summary`
- `Categorized Risks`
- `Event Timeline`
- `Notes`

The console should show messages similar to:

- collector start notices
- collector failure notices when live logs are unavailable
- fallback seeding notices
- severity counts
- findings with timestamps

## Project Status

This repository has completed the documented phase sequence up through report generation and documentation.

## Notes for Contributors

- Keep changes aligned with the current phase plan
- Do not skip ahead to later phases without explicit instruction
- Keep comments clear and professional so the flow stays easy to follow for the next developer


# Multi-Platform Log Correlation Pipeline

Multi-Platform Log Correlation Pipeline collects Linux and Windows failed-login data, correlates it against a known-machine baseline, and writes a structured security report.

## What It Does

- Reads Linux authentication failures from `/var/log/auth.log`
- Reads Windows failed logon events from Security Event ID `4625`
- Loads fallback inputs from `data/` when live collection is unavailable
- Flags suspicious activity as `CRITICAL`, `HIGH`, or `MEDIUM`
- Writes a readable report to `output/final_security_report.txt`
- Logs runtime activity to `logs/system.log`

## Inputs

- Linux collector output: `data/linux_data.json`
- Windows collector output: `data/windows_data.csv`
- Trusted baseline: `known_machines.csv`

## Outputs

- Runtime log: `logs/system.log`
- Final report: `output/final_security_report.txt`

## How to Run

Run the main Python entry point from the project root:

```powershell
python .\scripts\analyzer.py
```

What to expect:

- The Linux and Windows collectors are attempted first
- If live collection is unavailable, the program reads any existing files in `data/`
- If no usable log files exist in either location, the program logs:
  `No log files found in system or data folder`
  and exits cleanly
- When data is available, the report is written to `output/final_security_report.txt`

## How the Data Flow Works

1. The orchestrator starts both collectors.
2. Collector output is read from `data/`.
3. If collector output is missing, the program checks whether `data/` already contains usable log files.
4. If usable log files exist, they are used as fallback input.
5. If nothing is available, the program exits safely after logging the error.
6. Correlation rules are applied.
7. The final report is generated.

## Correlation Rules

- `Unknown IP -> CRITICAL`
- `>= 5 failed attempts -> HIGH`
- `Off-hours login -> MEDIUM`

The trusted-machine baseline is loaded from `known_machines.csv` for fast lookup.

## CI/CD

The repository includes GitHub Actions workflows that validate:

- Bash syntax with `shellcheck`
- Python syntax with `python -m py_compile`
- Required project files and folders

There is also a release workflow that gates the `release` branch on the same verification checks before promotion.

## Quick Verification

After running the program, confirm:

- `logs/system.log` contains the runtime messages
- `output/final_security_report.txt` exists and contains the summary, categorized risks, and event timeline
- The program exits cleanly with an error if neither system logs nor fallback data are present


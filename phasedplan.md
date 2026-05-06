Multi-Platform Log Correlation Pipeline — Phased Implementation Plan
Phase 1 — Project Initialization + CI Foundation (MANDATORY FIRST STEP)
Objective

Establish repository, structure, CI pipeline, and baseline standards.

Codex Task

Initialize Git repository:

git init

Create folder structure:

/project-root
├── scripts/
│ ├── linux_collector.sh
│ ├── windows_collector.ps1
│ └── analyzer.py
├── data/
├── logs/
├── output/
├── .github/workflows/
├── README.md
└── requirements.txt
Create .github/workflows/verify-scripts.yml:
Ubuntu runner
Install:
Python
shellcheck
Steps:
Run shellcheck scripts/linux_collector.sh
Run python -m py_compile scripts/analyzer.py
Validate file structure (check required files exist)
Testing
Push repo → verify GitHub Actions runs successfully
Commit
git add .
git commit -m "init: project structure and CI pipeline with GitHub Actions"
Phase 2 — Logging Framework (Cross-platform)
Objective

Unified logging system (console + file)

Codex Task
Implement logging utility in Python:
logs to:
console
/logs/system.log
Add reusable logging functions:
log_info()
log_warning()
log_error()
Ensure timestamp + severity format
Bash & PowerShell:
append logs to same file
Testing
Run Python script → confirm logs written to file + console
Commit
git commit -m "feat: unified logging system for console and file output"
Phase 3 — Linux Collector (Real + Fallback Ready)
Objective

Extract auth logs or fail gracefully

Codex Task
Script: linux_collector.sh
Features:

Try:

/var/log/auth.log
If fail:
log error
exit with status
Extract:
Failed password attempts
Output JSON → /data/linux_data.json
Comment every parsing step
Testing
Run on Linux OR simulate missing file
Validate:
JSON output
Proper error logging
Commit
git commit -m "feat: linux collector with real log parsing and error handling"
Phase 4 — Windows Collector (Event Log + Fallback Ready)
Objective

Extract Windows Security logs

Codex Task
Script: windows_collector.ps1

Use:

Get-WinEvent
Filter:
Event ID 4625

Export:

/data/windows_data.csv
Handle:
permission issues
missing logs
Full inline comments
Testing
Run PowerShell script
Validate CSV output
Commit
git commit -m "feat: windows collector using event logs with filtering and export"
Phase 5 — Data Fallback System + Seeder
Objective

Fallback when real logs unavailable

Codex Task
Python:
Detect if collectors failed or no data
Load logs from /data/
Seeder script:
Generate:
Linux auth.log style entries
Windows event CSV
Include:
brute force (>5 attempts)
lateral movement
normal logins
Seeder runs ONLY if data folder empty
Testing
Delete logs → run → verify fallback triggers
Verify seeded logs realistic
Commit
git commit -m "feat: fallback system with realistic log seeding for testing scenarios"
Phase 6 — Correlation Engine (Core Logic)
Objective

Central intelligence

Codex Task
Python:
Load:
JSON (Linux)
CSV (Windows)
known_machines.csv
Implement rules:
Unknown IP → CRITICAL
≥5 attempts → HIGH
Off-hours → MEDIUM
Use dictionaries for counting
Fully commented logic
Testing
Use seeded data
Validate rule triggers
Commit
git commit -m "feat: correlation engine with anomaly detection rules"
Phase 7 — Runtime Orchestrator (Main Flow)
Objective

Full execution pipeline

Codex Task
Python main flow:
Run Linux collector
Run Windows collector
If failure → fallback
Log everything (console + file)
Capture subprocess errors
Ensure:
no crash on failure
graceful continuation
Testing
Simulate:
missing logs
permission denied
Verify behavior
Commit
git commit -m "feat: orchestrator handling collectors, fallback, and runtime error management"
Phase 8 — Report Generation
Objective

Professional output

Codex Task

Generate:

/output/final_security_report.txt
Include:
Summary
categorized risks
timestamps
Format clean and readable
Testing
Validate report correctness
Commit
git commit -m "feat: final security report generation with structured output"
Phase 9 — README + Documentation (CD Requirement)
Objective

Meet Definition of Done

Codex Task
Write README:
architecture
setup steps
execution flow
fallback explanation
CI/CD explanation
Include:
how to test
example outputs
Testing
Follow README → verify reproducibility
Commit
git commit -m "docs: complete README with usage, architecture, and CI/CD workflow"
Phase 10 — Release Workflow (CD Implementation)
Objective

Production readiness

Codex Task
Extend GitHub Actions:
On main success → allow merge to release
Define:
release branch workflow
Ensure:
CI must pass before merge
Testing
Simulate PR → verify checks block/allow merge
Commit
git commit -m "ci: add release workflow enforcing CI/CD delivery rules"
Execution Rules for Codex (Critical)
Each phase:
Implement ONLY that phase
Test before moving forward
Commit immediately
Code requirements:
Every function must be commented
Important logic must have inline comments
Runtime requirements:
ALWAYS log:
success
failure
fallback usage
NEVER:
crash on missing logs
assume environment works
End State (What You Will Have)

A production-style pipeline that:

Pulls real logs (Linux + Windows)
Falls back safely
Detects attacks
Logs everything
Generates reports
Follows CI/CD strictly
Is fully documented
Is version-controlled with clean history

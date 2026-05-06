# Phase 2 logging helpers for the Windows side of the pipeline.
# The actual Event Log collection logic is intentionally deferred to later phases.

# Resolve the repository root so the script writes to the shared log file.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$LogDir = Join-Path $RepoRoot 'logs'
$LogFile = Join-Path $LogDir 'system.log'

# Create the log directory if it does not already exist.
if (-not (Test-Path -Path $LogDir)) {
    New-Item -Path $LogDir -ItemType Directory | Out-Null
}

function Write-LogMessage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Level,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    # Build the shared timestamped log entry once so console and file match.
    $Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $Line = "$Timestamp | $Level | $Message"

    # Append to the shared log file using UTF-8 so the format stays portable.
    Add-Content -Path $LogFile -Value $Line -Encoding UTF8

    # Echo the same line to the console for immediate feedback during execution.
    Write-Host $Line
}

function Write-LogInfo {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-LogMessage -Level 'INFO' -Message $Message
}

function Write-LogWarning {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-LogMessage -Level 'WARNING' -Message $Message
}

function Write-LogError {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-LogMessage -Level 'ERROR' -Message $Message
}

# Phase 2 verification hook: emit a sample log line when the script is run.
Write-LogInfo -Message 'Windows logging helper initialized.'


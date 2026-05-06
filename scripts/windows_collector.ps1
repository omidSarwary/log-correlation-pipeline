# Phase 4 Windows collector.
# This script reads Security log events with Event ID 4625, extracts the
# fields needed by the analysis engine, and exports them as a CSV file.

$ErrorActionPreference = 'Stop'

# Resolve repository-local paths so all outputs stay inside the project tree.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$LogDir = Join-Path $RepoRoot 'logs'
$LogFile = Join-Path $LogDir 'system.log'
$DataDir = Join-Path $RepoRoot 'data'
$OutputFile = Join-Path $DataDir 'windows_data.csv'

# Ensure the output directories exist before any write operations occur.
if (-not (Test-Path -Path $LogDir)) {
    New-Item -Path $LogDir -ItemType Directory | Out-Null
}

if (-not (Test-Path -Path $DataDir)) {
    New-Item -Path $DataDir -ItemType Directory | Out-Null
}

function Write-LogMessage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Level,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    # Build one standard line so console and file output stay identical.
    $Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $Line = "$Timestamp | $Level | $Message"

    # Console output provides immediate visibility during testing and CI runs.
    Write-Host $Line

    # Append to the shared log file so later phases can correlate outcomes.
    Add-Content -Path $LogFile -Value $Line -Encoding UTF8
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

function Get-EventFieldValue {
    param(
        [Parameter(Mandatory = $true)]
        [xml]$EventXml,

        [Parameter(Mandatory = $true)]
        [string]$FieldName
    )

    # Windows Security events store structured fields inside the event XML.
    $DataNode = $EventXml.Event.EventData.Data | Where-Object { $_.Name -eq $FieldName } | Select-Object -First 1
    if ($null -ne $DataNode) {
        return [string]$DataNode.'#text'
    }

    return ''
}

function Convert-ToCollectorRow {
    param(
        [Parameter(Mandatory = $true)]
        $Event
    )

    # Convert each event to XML so we can reliably access named Security fields.
    $EventXml = [xml]$Event.ToXml()

    [pscustomobject]@{
        TargetUserName = Get-EventFieldValue -EventXml $EventXml -FieldName 'TargetUserName'
        IpAddress      = Get-EventFieldValue -EventXml $EventXml -FieldName 'IpAddress'
        TimeCreated    = $Event.TimeCreated.ToString('s')
    }
}

function Export-EmptyCsv {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    # Create a header-only CSV so downstream steps can still load the file.
    @'
"TargetUserName","IpAddress","TimeCreated"
'@ | Set-Content -Path $Path -Encoding UTF8
}

try {
    Write-LogInfo -Message 'Starting Windows collector for Security Event ID 4625.'

    # Read the last 24 hours of failed logon events from the Security log.
    $StartTime = (Get-Date).AddHours(-24)
    $Filter = @{
        LogName   = 'Security'
        Id        = 4625
        StartTime = $StartTime
    }

    $Events = Get-WinEvent -FilterHashtable $Filter -ErrorAction Stop

    # Build the list of rows that will be written to the CSV export.
    $Rows = foreach ($Event in $Events) {
        Convert-ToCollectorRow -Event $Event
    }

    if (@($Rows).Count -gt 0) {
        # Export the selected fields without type metadata for clean Python parsing.
        $Rows | Export-Csv -Path $OutputFile -NoTypeInformation -Encoding UTF8
        Write-LogInfo -Message "Windows collector wrote CSV output to $OutputFile"
    }
    else {
        # Still create a valid CSV file so the pipeline has a predictable output.
        Export-EmptyCsv -Path $OutputFile
        Write-LogWarning -Message 'No Security Event ID 4625 entries were found in the last 24 hours.'
    }
}
catch [System.UnauthorizedAccessException] {
    Write-LogError -Message 'Permission denied while reading the Windows Security log.'
    exit 1
}
catch {
    # Surface missing-log and access issues in a single safe failure path.
    Write-LogError -Message "Windows collector failed: $($_.Exception.Message)"
    exit 1
}

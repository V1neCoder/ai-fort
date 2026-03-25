param(
    [Parameter(Mandatory = $true)]
    [string]$SessionId,

    [int]$CycleNumber = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $RepoRoot ".venv"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"
$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"

if (Test-Path $ActivateScript) {
    . $ActivateScript
} else {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $PythonCommand) {
        throw "Virtual environment not found and no python executable is available on PATH."
    }
    $PythonExe = $PythonCommand.Source
}

$SessionPath = Join-Path (Join-Path $RepoRoot "data\sessions") $SessionId
if (-not (Test-Path $SessionPath)) {
    throw "Session path not found: $SessionPath"
}

$SessionJsonPath = Join-Path $SessionPath "session.json"
if (-not (Test-Path $SessionJsonPath)) {
    throw "Missing session.json: $SessionJsonPath"
}

$Session = Get-Content $SessionJsonPath -Raw | ConvertFrom-Json
if ($CycleNumber -le 0) {
    $CycleNumber = [int]$Session.last_cycle_number
}

if ($CycleNumber -le 0) {
    throw "No cycle number found to validate."
}

$CycleTag = "{0:D4}" -f $CycleNumber
$SceneStatePath = Join-Path $SessionPath ("scene_state\cycle_{0}.json" -f $CycleTag)
if (-not (Test-Path $SceneStatePath)) {
    throw "Scene state file not found: $SceneStatePath"
}

$ActionHistoryPath = Join-Path $SessionPath "action_history.jsonl"
if (-not (Test-Path $ActionHistoryPath)) {
    throw "Action history file not found: $ActionHistoryPath"
}

$ActionRecord = Get-Content $ActionHistoryPath |
    Where-Object { $_.Trim() -ne "" } |
    ForEach-Object { $_ | ConvertFrom-Json } |
    Where-Object { [int]$_.cycle_number -eq $CycleNumber } |
    Select-Object -Last 1

if ($null -eq $ActionRecord) {
    throw "No action record found for cycle $CycleNumber"
}

$ActionJsonPath = Join-Path $SessionPath ("action_cycle_{0}.json" -f $CycleTag)
$ActionRecord.action | ConvertTo-Json -Depth 30 | Set-Content -Encoding UTF8 $ActionJsonPath

$DirtyZoneJsonPath = Join-Path $SessionPath ("dirty_zone_cycle_{0}.json" -f $CycleTag)
$DirtyZoneResultRaw = & $PythonExe -m apps.mcp_extensions.scene_tools dirty-zone `
    --scene-state-json $SceneStatePath `
    --cycle-number $CycleNumber `
    --repo-root $RepoRoot

$DirtyZoneResult = $DirtyZoneResultRaw | ConvertFrom-Json
if ($DirtyZoneResult.status -ne "ok") {
    throw "Could not derive dirty zone for cycle $CycleNumber"
}

$DirtyZoneResult.dirty_zone | ConvertTo-Json -Depth 30 | Set-Content -Encoding UTF8 $DirtyZoneJsonPath

Write-Host "Running validator pass..."
& $PythonExe -m apps.validation.run_validators `
    --repo-root $RepoRoot `
    --scene-state-path $SceneStatePath `
    --dirty-zone-path $DirtyZoneJsonPath `
    --action-path $ActionJsonPath

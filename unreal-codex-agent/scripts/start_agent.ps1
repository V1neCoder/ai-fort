param(
    [string]$Goal = "Build a polished room that fits the task.",
    [int]$Cycles = 1,
    [string]$SessionName = "",
    [switch]$BootstrapIfMissing
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $RepoRoot ".venv"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"
$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"

if (Test-Path $ActivateScript) {
    . $ActivateScript
} elseif ($BootstrapIfMissing) {
    & (Join-Path $PSScriptRoot "bootstrap.ps1")
    if (-not (Test-Path $ActivateScript)) {
        throw "Bootstrap completed but the virtual environment activation script is still missing."
    }
    . $ActivateScript
} else {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $PythonCommand) {
        throw "Virtual environment not found and no python executable is available on PATH."
    }
    $PythonExe = $PythonCommand.Source
}

$Dirs = @(
    "data\catalog",
    "data\sessions",
    "data\previews",
    "data\uefn_bridge\captures",
    "data\cache\latest_shortlists",
    "data\cache\latest_scene_packets",
    "uefn\verse\generated",
    "logs"
)
foreach ($dir in $Dirs) {
    $full = Join-Path $RepoRoot $dir
    if (-not (Test-Path $full)) {
        New-Item -ItemType Directory -Force -Path $full | Out-Null
    }
}

$Args = @(
    "-m", "apps.orchestrator.main",
    "start",
    "--repo-root", $RepoRoot,
    "--goal", $Goal,
    "--cycles", "$Cycles"
)

if ($SessionName -ne "") {
    $Args += @("--session-name", $SessionName)
}

Write-Host "Starting agent..."
Write-Host "Goal: $Goal"
& $PythonExe @Args

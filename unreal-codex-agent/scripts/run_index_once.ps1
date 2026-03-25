param(
    [string]$RawInput = ""
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

$Args = @(
    "-m", "apps.asset_ai.build_full_index",
    "--repo-root", $RepoRoot
)

if ($RawInput -ne "") {
    $Args += @("--raw-input", $RawInput)
}

Write-Host "Running asset catalog index..."
& $PythonExe @Args

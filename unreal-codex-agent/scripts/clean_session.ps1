param(
    [string]$SessionId = "",
    [switch]$All,
    [switch]$RemoveCache
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$SessionsRoot = Join-Path $RepoRoot "data\sessions"
$CacheShortlists = Join-Path $RepoRoot "data\cache\latest_shortlists"
$CacheScenePackets = Join-Path $RepoRoot "data\cache\latest_scene_packets"

if (-not (Test-Path $SessionsRoot)) {
    Write-Host "No sessions directory found."
    exit 0
}

if ($All) {
    Write-Host "Removing all session folders..."
    Get-ChildItem -Path $SessionsRoot -Directory | ForEach-Object {
        Remove-Item $_.FullName -Recurse -Force
        Write-Host "Removed $($_.FullName)"
    }
}
elseif ($SessionId -ne "") {
    $Target = Join-Path $SessionsRoot $SessionId
    if (Test-Path $Target) {
        Remove-Item $Target -Recurse -Force
        Write-Host "Removed $Target"
    } else {
        Write-Host "Session not found: $Target"
    }
}
else {
    throw "Provide -SessionId <id> or use -All."
}

if ($RemoveCache) {
    Write-Host "Cleaning cache JSON files..."
    foreach ($cacheDir in @($CacheShortlists, $CacheScenePackets)) {
        if (Test-Path $cacheDir) {
            Get-ChildItem -Path $cacheDir -File -Filter *.json | ForEach-Object {
                Remove-Item $_.FullName -Force
                Write-Host "Removed cache file $($_.FullName)"
            }
        }
    }
}

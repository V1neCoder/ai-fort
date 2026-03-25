param(
    [string]$UnrealProjectPath = "",
    [string]$PluginFolderName = "Prefabricator",
    [string]$RepoUrl = "https://github.com/unknownworlds/prefabricator-ue5"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($UnrealProjectPath)) {
    $UnrealProjectPath = $env:UNREAL_PROJECT_PATH
}

if ([string]::IsNullOrWhiteSpace($UnrealProjectPath)) {
    $UnrealProjectPath = $env:UEFN_PROJECT_PATH
}

if ([string]::IsNullOrWhiteSpace($UnrealProjectPath)) {
    throw "Provide -UnrealProjectPath or set UNREAL_PROJECT_PATH. This helper is for a desktop Unreal reference project, not the primary UEFN runtime."
}

$ProjectFile = Resolve-Path $UnrealProjectPath -ErrorAction Stop
if ($ProjectFile.Path.ToLower().EndsWith(".uefnproject")) {
    throw "Prefabricator installation is reference-only here and expects a desktop Unreal .uproject, not a .uefnproject."
}
$ProjectDir = Split-Path -Parent $ProjectFile
$PluginsDir = Join-Path $ProjectDir "Plugins"
$TargetDir = Join-Path $PluginsDir $PluginFolderName

New-Item -ItemType Directory -Force -Path $PluginsDir | Out-Null

$Git = Get-Command git -ErrorAction SilentlyContinue
if ($null -eq $Git) {
    throw "git is required to install Prefabricator UE5."
}

if (Test-Path (Join-Path $TargetDir ".git")) {
    Write-Host "Updating existing Prefabricator plugin at $TargetDir"
    & $Git.Source -C $TargetDir pull --ff-only
} elseif (Test-Path $TargetDir) {
    throw "Target plugin directory already exists and is not a git repository: $TargetDir"
} else {
    Write-Host "Cloning Prefabricator UE5 into $TargetDir"
    & $Git.Source clone $RepoUrl $TargetDir
}

$Manifest = Get-ChildItem -Path $TargetDir -Filter *.uplugin -File -Recurse | Select-Object -First 1
if ($null -eq $Manifest) {
    throw "No .uplugin file was found after installation."
}

Write-Host ""
Write-Host "Installed Prefabricator UE5:"
Write-Host "  Project: $ProjectFile"
Write-Host "  Plugin:  $TargetDir"
Write-Host "  Manifest:$($Manifest.FullName)"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Open the desktop Unreal reference project."
Write-Host "  2. Enable the Prefabricator plugin if Unreal prompts you."
Write-Host "  3. Rebuild the project if Unreal requests a compile."

param(
  [string]$ProjectRoot = "C:\Users\Public\MoniK\smart-home-monik_sdk75+e",
  [string]$OriginalProjectRoot = "C:\Users\Public\MoniK\smart-home-monik",
  [string]$BackupRoot = "backups"
)

$ErrorActionPreference = "Stop"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$destination = Join-Path $BackupRoot "android-before-test-$timestamp"

$paths = @(
  "App.tsx",
  "package.json",
  "android\app\src\main\AndroidManifest.xml",
  "android\app\build.gradle",
  "android\build.gradle",
  "android\app\src\main\java",
  "android\app\src\main\kotlin"
)

function BackupProject($sourceRoot, $label) {
  $projectDestination = Join-Path $destination $label
  New-Item -ItemType Directory -Force -Path $projectDestination | Out-Null

  foreach ($relativePath in $paths) {
    $source = Join-Path $sourceRoot $relativePath
    if (Test-Path $source) {
      $target = Join-Path $projectDestination $relativePath
      $targetParent = Split-Path $target -Parent
      New-Item -ItemType Directory -Force -Path $targetParent | Out-Null
      Copy-Item -Path $source -Destination $target -Recurse -Force
      Write-Host "Backed up $source -> $target" -ForegroundColor Green
    } else {
      Write-Host "Skipped missing $source" -ForegroundColor Yellow
    }
  }
}

New-Item -ItemType Directory -Force -Path $destination | Out-Null
Write-Host "Updated project root: $ProjectRoot" -ForegroundColor Cyan
BackupProject $ProjectRoot "updated-sdk75e"

if ($OriginalProjectRoot -and (Test-Path $OriginalProjectRoot)) {
  Write-Host "`nOriginal project root: $OriginalProjectRoot" -ForegroundColor Cyan
  BackupProject $OriginalProjectRoot "original"
}

Write-Host "`nBackup ready: $destination" -ForegroundColor Green

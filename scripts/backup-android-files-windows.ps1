param(
  [string]$ProjectRoot = "C:\Users\Public\MoniK\smart-home-monik",
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

New-Item -ItemType Directory -Force -Path $destination | Out-Null

foreach ($relativePath in $paths) {
  $source = Join-Path $ProjectRoot $relativePath
  if (Test-Path $source) {
    $target = Join-Path $destination $relativePath
    $targetParent = Split-Path $target -Parent
    New-Item -ItemType Directory -Force -Path $targetParent | Out-Null
    Copy-Item -Path $source -Destination $target -Recurse -Force
    Write-Host "Backed up $source -> $target" -ForegroundColor Green
  } else {
    Write-Host "Skipped missing $source" -ForegroundColor Yellow
  }
}

Write-Host "`nBackup ready: $destination" -ForegroundColor Green

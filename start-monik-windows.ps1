param(
  [switch]$Update,
  [switch]$ResetLocalChanges,
  [string]$AndroidRoot = 'C:\Users\Public',
  [string]$AdbPath = ''
)

$ErrorActionPreference = "Stop"

function Run($command, $arguments = @()) {
  Write-Host "`n> $command $($arguments -join ' ')" -ForegroundColor Cyan
  & $command @arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed: $command $($arguments -join ' ')"
  }
}

if (-not $AdbPath) {
  $AdbPath = Join-Path $AndroidRoot 'platform-tools\adb.exe'
}

$env:ANDROID_HOME = $AndroidRoot
$env:ANDROID_SDK_ROOT = $AndroidRoot
$env:ADB_PATH = $AdbPath
$env:PATH = "$(Join-Path $AndroidRoot 'platform-tools');$(Join-Path $AndroidRoot 'emulator');$(Join-Path $AndroidRoot 'cmdline-tools\latest\bin');$env:PATH"

Write-Host "MoniK automatic Windows starter" -ForegroundColor Green
Write-Host "Folder: $PWD"
Write-Host "ADB path: $AdbPath"

Run "node" @("-v")
Run "npm" @("-v")

if ($Update) {
  if (Test-Path ".git") {
    if ($ResetLocalChanges) {
      Write-Host "`nResetLocalChanges is ON: local uncommitted changes will be discarded." -ForegroundColor Yellow
      Run "git" @("reset", "--hard")
      Run "git" @("clean", "-fd")
    }

    Run "git" @("fetch", "origin")
    Run "git" @("pull", "--ff-only")
  } else {
    Write-Host "`nNo .git folder found. Skipping git update; this looks like a ZIP download." -ForegroundColor Yellow
  }
}

Run "npm" @("install")
Run "npm" @("run", "check")
Run "npm" @("run", "test:page")

Write-Host "`nOpening http://localhost:4173 ..." -ForegroundColor Green
Start-Process "http://localhost:4173"

Run "npm" @("start")

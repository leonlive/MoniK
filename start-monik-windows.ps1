param(
  [switch]$Update,
  [switch]$ResetLocalChanges,
  [string]$AndroidRoot = 'C:\Users\Public',
  [string]$AdbPath = '',
  [switch]$SkipChecks
)

$ErrorActionPreference = "Stop"
$script:HadError = $false

function Wait-BeforeExit() {
  Write-Host ""
  Write-Host "============================================================" -ForegroundColor DarkGray
  if ($script:HadError) {
    Write-Host "MoniK starter stopped because of an error. The window stays open so you can copy the error." -ForegroundColor Red
  } else {
    Write-Host "MoniK starter finished/stopped. The window stays open so you can read the log." -ForegroundColor Yellow
  }
  Write-Host "Press ENTER to close this window..." -ForegroundColor Yellow
  [void][System.Console]::ReadLine()
}

function Run($command, $arguments = @()) {
  Write-Host "`n> $command $($arguments -join ' ')" -ForegroundColor Cyan
  & $command @arguments
  $exitCode = $LASTEXITCODE
  if ($null -ne $exitCode -and $exitCode -ne 0) {
    throw "Command failed with exit code $exitCode`: $command $($arguments -join ' ')"
  }
}

try {
  if ($PSScriptRoot) {
    Set-Location $PSScriptRoot
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
  Write-Host "Node server URL: http://localhost:4173"

  if (-not (Test-Path "package.json")) {
    throw "package.json was not found. Start this script from the MoniK repository folder or keep it in the repo root."
  }

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

  if (-not $SkipChecks) {
    Run "npm" @("run", "check")
    Run "npm" @("run", "test:page")
  } else {
    Write-Host "`nSkipChecks is ON: npm run check/test:page skipped." -ForegroundColor Yellow
  }

  Write-Host "`nStarting MoniK server. Do NOT close this window while testing." -ForegroundColor Green
  Write-Host "If the browser opens before the server is ready, refresh it after 2-3 seconds." -ForegroundColor Yellow
  Start-Process "http://localhost:4173"

  Run "npm" @("start")
} catch {
  $script:HadError = $true
  Write-Host ""
  Write-Host "ERROR:" -ForegroundColor Red
  Write-Host $_.Exception.Message -ForegroundColor Red
  Write-Host ""
  Write-Host "Common fixes:" -ForegroundColor Yellow
  Write-Host "1. Install Node.js 20+ and reopen CMD/PowerShell."
  Write-Host "2. Run from the repo folder: C:\Users\Public\github\leonlive-MoniK\MoniK"
  Write-Host "3. If port 4173 is busy, close the old MoniK server window."
  Write-Host "4. If scripts are blocked, run: powershell -ExecutionPolicy Bypass -File .\start-monik-windows.ps1"
} finally {
  Wait-BeforeExit
}

param(
  [switch]$Update,
  [switch]$ResetLocalChanges
)

$ErrorActionPreference = "Stop"

function Run($command, $arguments = @()) {
  Write-Host "`n> $command $($arguments -join ' ')" -ForegroundColor Cyan
  & $command @arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed: $command $($arguments -join ' ')"
  }
}

Write-Host "MoniK automatic Windows starter" -ForegroundColor Green
Write-Host "Folder: $PWD"

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

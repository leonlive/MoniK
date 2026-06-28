param(
  [string]$Output = "monik-login.log",
  [string]$Filter = "tuya smartlife thing kt login error success false schema country client account home device bridge native method"
)

$ErrorActionPreference = "Stop"

function Run($command, $arguments = @()) {
  Write-Host "`n> $command $($arguments -join ' ')" -ForegroundColor Cyan
  & $command @arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed: $command $($arguments -join ' ')"
  }
}

Run "adb" @("devices")
Run "adb" @("logcat", "-c")

Write-Host "`nNow press the MoniK login/import button on the phone." -ForegroundColor Yellow
Read-Host "Press ENTER here after the phone shows success or error"

Run "adb" @("logcat", "-d", "-t", "1500") | Out-File -Encoding utf8 $Output

Write-Host "`nSaved log to $Output" -ForegroundColor Green
Write-Host "Filtered lines:" -ForegroundColor Green
findstr /i $Filter $Output

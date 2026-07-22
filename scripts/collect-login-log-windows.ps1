param(
  [string]$AndroidRoot = "C:\Users\Public",
  [string]$AdbPath = "",
  [string]$Output = "monik-login.log",
  [string]$Filter = "tuya smartlife thing kt login error success false schema country client account home device bridge native method",
  [switch]$SkipClear
)

$ErrorActionPreference = "Stop"

if (-not $AdbPath) {
  $AdbPath = Join-Path $AndroidRoot "platform-tools\adb.exe"
}

$env:ANDROID_HOME = $AndroidRoot
$env:ANDROID_SDK_ROOT = $AndroidRoot
$env:ADB_PATH = $AdbPath
$env:PATH = "$(Join-Path $AndroidRoot 'platform-tools');$(Join-Path $AndroidRoot 'emulator');$(Join-Path $AndroidRoot 'cmdline-tools\latest\bin');$env:PATH"

function Run($command, $arguments = @()) {
  Write-Host "`n> $command $($arguments -join ' ')" -ForegroundColor Cyan
  & $command @arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed: $command $($arguments -join ' ')"
  }
}

Write-Host "ADB path: $AdbPath" -ForegroundColor Green
Run $AdbPath @("devices")

if (-not $SkipClear) {
  Run $AdbPath @("logcat", "-c")
} else {
  Write-Host "Skipping adb logcat -c." -ForegroundColor Yellow
}

Write-Host "`nNow press the MoniK login/import button on the phone." -ForegroundColor Yellow
Read-Host "Press ENTER here after the phone shows success or error"

Run $AdbPath @("logcat", "-d", "-t", "1500") | Out-File -Encoding utf8 $Output

Write-Host "`nSaved log to $Output" -ForegroundColor Green
Write-Host "Filtered lines:" -ForegroundColor Green
findstr /i $Filter $Output

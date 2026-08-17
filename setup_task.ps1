#Requires -RunAsAdministrator
# Registers the depop-pinger check as a Windows scheduled task.
# Re-runnable: -Force overwrites the existing task cleanly.
#
# Why local hosting: GitHub Actions runner IPs are Cloudflare-blocked by
# depop.com (every cron run 2026-08-15..17 got HTTP 403), and Task
# Scheduler at 2 min also beats the cron's real 25-60 min cadence for
# listings that sell in minutes.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$TrackerScript = Join-Path $ProjectRoot "tracker.py"
$TaskPath = "\DepopPinger\"
$TaskName = "Check Listings"
# Poll cadence. 2 min respects the repo's 60s-minimum rate-limit rule with
# margin; do not go below 1 minute.
$RepeatMinutes = 2

if (-not (Test-Path $VenvPython)) {
    throw "Venv python not found at $VenvPython. Create it first: python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
}
if (-not (Test-Path (Join-Path $ProjectRoot ".env"))) {
    throw ".env not found in $ProjectRoot. It must contain NTFY_TOPIC=<topic> or alerts will crash."
}

$Action = New-ScheduledTaskAction `
    -Execute $VenvPython `
    -Argument "`"$TrackerScript`"" `
    -WorkingDirectory $ProjectRoot

$Trigger = New-ScheduledTaskTrigger `
    -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $RepeatMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

# S4U: runs whether logged on or not, no stored password. NEVER leave the
# default Interactive logon -- Interactive-only tasks silently stop firing
# on sleep/lock/logoff (root cause of the 2026-07 daily-briefing outage).
$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType S4U `
    -RunLevel Highest

$Settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -MultipleInstances IgnoreNew

# Defaults block/kill tasks on battery -- explicitly allow both.
$Settings.DisallowStartIfOnBatteries = $false
$Settings.StopIfGoingOnBatteries = $false

Register-ScheduledTask `
    -TaskPath $TaskPath `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Description "depop-pinger: poll Depop for Lululemon Speed Up listings every $RepeatMinutes min, push matches via ntfy.sh. Criteria live in config.py; logs in data\logs\tracker.log." `
    -Force | Out-Null

Write-Host "Registered $TaskPath$TaskName (every $RepeatMinutes min, S4U, wake-to-run, battery-safe)."
Write-Host ""
Write-Host "Verify with:"
Write-Host "  Get-ScheduledTask -TaskPath '$TaskPath'"
Write-Host "  Start-ScheduledTask -TaskPath '$TaskPath' -TaskName '$TaskName'"
Write-Host "  (Get-ScheduledTaskInfo -TaskPath '$TaskPath' -TaskName '$TaskName').LastTaskResult   # 0 = ok"
Write-Host "  Get-Content data\logs\tracker.log -Tail 5"
Write-Host ""
Write-Host "Wake timers must be allowed for -WakeToRun to work from sleep:"
Write-Host "  powercfg /query SCHEME_CURRENT SUB_SLEEP RTCWAKE"

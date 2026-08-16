# Create (or replace) the logon task that starts the hidden EYEWAZ voice server.
# Called by the installer at post-install. Uses Register-ScheduledTask rather than
# `schtasks /tr "..."` because the install path contains a space ("Program Files")
# and schtasks' /tr quoting is fragile - the cmdlet handles the quoting for us.
# Self-locating: the server launcher sits next to this script in the install dir.
$vbs       = Join-Path $PSScriptRoot 'start-server.vbs'
$action    = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('"' + $vbs + '"')
$trigger   = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -GroupId 'BUILTIN\Users' -RunLevel Limited
Register-ScheduledTask -TaskName 'EYEWAZ Urdu Voice Server' `
    -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null

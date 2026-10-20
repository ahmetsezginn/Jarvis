# Opt-in installed Windows service test; no recordings or model-generated machine actions.
[CmdletBinding()]
param([switch]$Acoustic)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$statusFile = Join-Path $env:ProgramData 'JARVIS\Wake\status.json'
$launcher = Join-Path $env:ProgramFiles 'JARVIS\Wake\jarvis-wake-service.exe'
$scheduler = New-Object -ComObject Schedule.Service
$scheduler.Connect()
$task = $scheduler.GetFolder('\JARVIS').GetTask('Launch')
function Read-Wake {
    foreach ($attempt in 1..5) {
        try { return Get-Content -LiteralPath $statusFile -Raw | ConvertFrom-Json } catch { Start-Sleep -Milliseconds 100 }
    }
    throw 'Could not read the installed wake status.'
}
function Wait-Phase([string]$Expected) {
    $deadline = [DateTime]::UtcNow.AddSeconds(35)
    do {
        $current = Read-Wake
        if ($current.phase -eq $Expected) { return $current }
        if ([DateTime]::UtcNow -gt $deadline) { throw "Timed out waiting for $Expected. Status: $($current | ConvertTo-Json -Compress)" }
        Start-Sleep -Milliseconds 200
    } while ($true)
}
if ($task.State -eq 4) { throw 'Close the current JARVIS desktop before this test.' }
$initial = Wait-Phase 'listening'
if (-not $initial.microphone_open) { throw 'Service is not listening.' }
Suspend-Service JarvisWake
$paused = Wait-Phase 'paused'
if ($paused.microphone_open) { throw 'Pause retained the microphone.' }
Resume-Service JarvisWake
$resumed = Wait-Phase 'listening'
if (-not $resumed.microphone_open) { throw 'Resume did not acquire microphone.' }
if ($Acoustic) {
    $wav = Join-Path $projectRoot 'target\wake-fixtures\wake-en.wav'
    if (-not (Test-Path -LiteralPath $wav -PathType Leaf)) { throw 'Explicit synthetic wake WAV fixture is missing.' }
    $player = New-Object Media.SoundPlayer($wav)
    try { $player.PlaySync() } finally { $player.Dispose() }
} else {
    $activation = Start-Process -FilePath $launcher -ArgumentList 'open' -WindowStyle Hidden -PassThru -Wait
    if ($activation.ExitCode -ne 0) { throw 'Installed fixed launcher failed.' }
}
$opened = Wait-Phase 'assistant_running'
if ($opened.microphone_open) { throw 'Service retained microphone while assistant is open.' }
foreach ($attempt in 1..3) {
    $activation = Start-Process -FilePath $launcher -ArgumentList 'open' -WindowStyle Hidden -PassThru -Wait
    if ($activation.ExitCode -ne 0) { throw 'Repeated fixed activation failed.' }
}
if ($task.GetInstances(0).Count -ne 1) { throw 'Repeated activation created multiple desktops.' }
$pythonConfig = Get-Content -LiteralPath (Join-Path $projectRoot 'services\brain\.venv\pyvenv.cfg') | Where-Object { $_ -match '^executable = ' } | Select-Object -First 1
$python = Join-Path $projectRoot 'services\brain\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { $python = $pythonConfig.Substring('executable = '.Length).Trim() }
$previousPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = ((Join-Path $projectRoot 'services\brain\src'),(Join-Path $projectRoot 'services\brain\.venv\Lib\site-packages'),$previousPath | Where-Object { $_ }) -join ';'
    # Wait for the real Qt lifecycle lease; the close still uses Core validation/policy.
    $closed = $false
    foreach ($attempt in 1..30) {
        & $python -c "from jarvis_brain.core.client import JarvisCoreClient; c=JarvisCoreClient(); c.connect(); print(c.execute_tool('desktop_close',{}).data); c.close()" 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { $closed = $true; break }
        Start-Sleep -Milliseconds 400
    }
    if (-not $closed) { throw 'Real desktop never attached to Core.' }
} finally { $env:PYTHONPATH = $previousPath }
$final = Wait-Phase 'listening'
if ($task.State -ne 3 -or $task.GetInstances(0).Count -ne 0) { throw 'JARVIS task did not exit.' }
if (-not $final.microphone_open) { throw 'Listener did not rearm.' }
if ($Acoustic -and $final.wake_count -le $initial.wake_count) { throw 'No real microphone wake was counted.' }
$result = [ordered]@{schema=1;acoustic=[bool]$Acoustic;pause_releases_microphone=$true;resume_rearms=$true;fixed_activation=$true;single_instance=$true;assistant_microphone_handoff=$true;native_policy_close=$true;rearmed_after_exit=$true;initial=$initial;final=$final}
$result | ConvertTo-Json -Depth 5 | Tee-Object -FilePath (Join-Path $projectRoot 'target\wake-service-smoke.json')

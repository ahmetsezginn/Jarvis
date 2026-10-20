# Opt-in real Windows lifecycle contract. Ends only the JARVIS task started by this test.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$projectRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$statusFile=Join-Path $env:ProgramData 'JARVIS\Wake\status.json'
$launcher=Join-Path $env:ProgramFiles 'JARVIS\Wake\jarvis-wake-service.exe'
$scheduler=New-Object -ComObject Schedule.Service
$scheduler.Connect()
$task=$scheduler.GetFolder('\JARVIS').GetTask('Launch')
if ($task.State -ne 3) {throw 'Close JARVIS before this opt-in lifecycle test.'}
$baselineCore=@(Get-Process -Name jarvis-core -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
function Wait-Task([int]$State) {
    $deadline=[DateTime]::UtcNow.AddSeconds(25)
    do {
        if ($task.State -eq $State) {return}
        if ([DateTime]::UtcNow -gt $deadline) {throw "Task did not reach state $State."}
        Start-Sleep -Milliseconds 100
    } while ($true)
}
function Open-Fixed {
    $activation=Start-Process -FilePath $launcher -ArgumentList 'open' -WindowStyle Hidden -PassThru -Wait
    if ($activation.ExitCode -ne 0) {throw 'Fixed desktop activation failed.'}
    Wait-Task 4
}
Stop-Service JarvisWake
try {
    # Manual desktop use must remain available without restarting the stopped listener.
    Open-Fixed
    Start-Sleep -Seconds 3
    if ((Get-Service JarvisWake).Status -ne 'Stopped') {throw 'Manual opening unexpectedly restarted microphone service.'}
    $processes=@(Get-CimInstance Win32_Process)
    $helper=@($processes | Where-Object {$_.Name -eq 'jarvis-wake-service.exe' -and $_.SessionId -ne 0 -and $_.CommandLine -match '\sdesktop\s*$'})
    if ($helper.Count -ne 1) {throw 'Expected exactly one user-context native task parent.'}
    $owned=@([uint32]$helper[0].ProcessId)
    foreach ($generation in 1..8) {
        $children=@($processes | Where-Object {$_.ParentProcessId -in $owned -and $_.ProcessId -notin $owned} | Select-Object -ExpandProperty ProcessId)
        if (-not $children.Count) {break}
        $owned += $children
    }
    if (@($processes | Where-Object {$_.ProcessId -in $owned -and $_.CommandLine -match 'services[\\/]desktop[\\/]main.py'}).Count -ne 1) {throw 'The real Qt process did not start.'}
    # Task Scheduler terminates the parent; its Windows job must take descendants with it.
    $task.Stop(0)
    Wait-Task 3
    $deadline=[DateTime]::UtcNow.AddSeconds(10)
    do {
        $alive=@($owned | Where-Object {Get-Process -Id $_ -ErrorAction SilentlyContinue})
        if (-not $alive.Count) {break}
        if ([DateTime]::UtcNow -gt $deadline) {throw "Orphaned task descendants: $alive"}
        Start-Sleep -Milliseconds 100
    } while ($true)
    foreach ($sharedId in $baselineCore) {if (-not (Get-Process -Id $sharedId -ErrorAction SilentlyContinue)) {throw 'An existing shared Core was killed.'}}
    [pscustomobject]@{schema=1;manual_when_listener_stopped=$true;listener_not_restarted=$true;forced_parent_exit_cleans_descendants=$true;owned_process_count=$owned.Count;shared_core_preserved=$true} | ConvertTo-Json | Tee-Object -FilePath (Join-Path $projectRoot 'target\wake-lifecycle-contract.json')
} finally {
    if ($task.State -eq 4) {$task.Stop(0)}
    Start-Service JarvisWake
}

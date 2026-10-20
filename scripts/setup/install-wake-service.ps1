[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^S-1-5-21-\d+-\d+-\d+-\d+$')][string]$OwnerSid,
    [Parameter(Mandatory=$true)][string]$OwnerAccount,
    [switch]$Remove,
    [switch]$DefaultMicrophone,
    [ValidatePattern('^[^"\r\n]{1,120}$')][string]$Microphone
)
$ErrorActionPreference = 'Stop'
if ($DefaultMicrophone -and $Microphone) { throw 'Choose the Windows default or an explicit microphone, not both.' }
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$log = Join-Path $projectRoot 'target\wake-install.log'
$serviceName = 'JarvisWake'
$installRoot = Join-Path $env:ProgramFiles 'JARVIS\Wake'
$statusRoot = Join-Path $env:ProgramData 'JARVIS\Wake'
$package = Join-Path $projectRoot 'target\wake-package'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Windows administrator approval is required to install/remove this service.' }
function Protect-Directory([string]$Path, [bool]$WritableStatus) {
    if ((Get-Item -LiteralPath $Path).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Refusing a reparse-point install directory.' }
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner((New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')))
    $entries = @(@('S-1-5-18','FullControl'),@('S-1-5-32-544','FullControl'),@($OwnerSid,'ReadAndExecute'),@('S-1-5-19',$(if ($WritableStatus) {'Modify'} else {'ReadAndExecute'})))
    foreach ($entry in $entries) {
        $sid = New-Object Security.Principal.SecurityIdentifier($entry[0])
        $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sid,$entry[1],'ContainerInherit,ObjectInherit','None','Allow')))
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}
function Invoke-Sc([string[]]$Arguments) {
    & "$env:SystemRoot\System32\sc.exe" @Arguments
    if ($LASTEXITCODE -ne 0) { throw "SCM operation failed: $($Arguments[0]) ($LASTEXITCODE)." }
}
Start-Transcript -Path $log -Force | Out-Null
try {
    $resolvedOwner = (New-Object Security.Principal.NTAccount($OwnerAccount)).Translate([Security.Principal.SecurityIdentifier]).Value
    if ($resolvedOwner -ne $OwnerSid) { throw 'The selected Windows account and SID do not match.' }
    $scheduler = New-Object -ComObject 'Schedule.Service'
    $scheduler.Connect()
    $root = $scheduler.GetFolder('\')
    $folder = $null
    try { $folder = $scheduler.GetFolder('\JARVIS') } catch { if (-not $Remove) { $folder = $root.CreateFolder('JARVIS') } }
    $existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if ($existingService) {
        $record = Get-CimInstance Win32_Service -Filter "Name='$serviceName'"
        $expected = '"' + (Join-Path $installRoot 'jarvis-wake-service.exe') + '" service'
        if ($record.PathName -ne $expected) { throw 'A different service uses JarvisWake; refusing to replace it.' }
        if ($record.StartName -ine 'NT AUTHORITY\LocalService') { throw 'Unexpected service identity; refusing to update.' }
        if ($existingService.Status -ne 'Stopped') { Stop-Service -Name $serviceName -Force }
        if ($record.ProcessId -gt 0 -and (Get-Process -Id $record.ProcessId -ErrorAction SilentlyContinue)) {
            Wait-Process -Id $record.ProcessId -Timeout 15 -ErrorAction SilentlyContinue
            if (Get-Process -Id $record.ProcessId -ErrorAction SilentlyContinue) { throw 'Previous service process did not exit; protected binaries were not replaced.' }
        }
    }
    if ($Remove) {
        if ($folder) { try { $folder.DeleteTask('Launch',0) } catch { Write-Warning $_ } }
        if ($existingService) { Invoke-Sc -Arguments @('delete',$serviceName) }
        Write-Host 'JARVIS wake service removed. Models, notes, tasks and the desktop are retained.'
        return
    }
    if (-not (Test-Path -LiteralPath (Join-Path $package 'runtime\manifest.json') -PathType Leaf)) { throw 'Prepare the native wake package before elevation.' }
    foreach ($parent in @((Join-Path $env:ProgramFiles 'JARVIS'),(Join-Path $env:ProgramData 'JARVIS'))) {
        if (Test-Path -LiteralPath $parent) { if ((Get-Item -LiteralPath $parent).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Refusing a reparse-point install parent.' } }
    }
    New-Item -ItemType Directory -Path $installRoot,$statusRoot -Force | Out-Null
    Protect-Directory $installRoot $false
    Protect-Directory $statusRoot $true
    $allowed = @('jarvis-wake-service.exe','provider.json','runtime/manifest.json','runtime/LICENSE.openwakeword-code','runtime/LICENSE.openwakeword-models','runtime/THIRD_PARTY.md')
    $pins = Get-Content -LiteralPath (Join-Path $package 'runtime\manifest.json') -Raw | ConvertFrom-Json
    $required = @('libLiteRt.dll','melspectrogram.tflite','embedding_model.tflite','hey_jarvis_v0.1.tflite')
    if (@($pins.PSObject.Properties).Count -ne $required.Count) { throw 'Unexpected artifact manifest.' }
    foreach ($name in $required) {
        $pin = $pins.PSObject.Properties[$name]
        if (-not $pin -or $pin.Value -notmatch '^[0-9a-f]{64}$') { throw 'Missing or invalid wake artifact pin.' }
        $source = Join-Path $package "runtime/$name"
        if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $pin.Value) { throw 'Native wake source artifact checksum mismatch.' }
        $allowed += "runtime/$name"
    }
    foreach ($name in $allowed) {
        $source = Join-Path $package $name
        $destination = Join-Path $installRoot $name
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        if ((Get-Item -LiteralPath (Split-Path -Parent $destination)).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Refusing a reparse-point artifact directory.' }
        if ((Test-Path -LiteralPath $destination) -and ((Get-Item -LiteralPath $destination).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Refusing a reparse-point artifact.' }
        Copy-Item -LiteralPath $source -Destination $destination -Force
        if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) { throw 'Protected install copy checksum mismatch.' }
    }
    if (-not $DefaultMicrophone -and -not $Microphone -and (Test-Path -LiteralPath (Join-Path $installRoot 'config.json'))) {
        $previous = Get-Content -LiteralPath (Join-Path $installRoot 'config.json') -Raw | ConvertFrom-Json
        if ($previous.owner_sid -eq $OwnerSid) { $Microphone=$previous.microphone }
    }
    $config = @{schema=1;owner_account=$OwnerAccount;owner_sid=$OwnerSid;repository=$projectRoot;powershell=(Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe');microphone=$(if ($Microphone) {$Microphone} else {$null})}
    [IO.File]::WriteAllText((Join-Path $installRoot 'config.json'),($config | ConvertTo-Json),(New-Object Text.UTF8Encoding($false)))
    $sddl = "O:BAG:BAD:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GRGX;;;LS)(A;;GRGX;;;$OwnerSid)"
    $folder.SetSecurityDescriptor($sddl,0)
    $definition = $scheduler.NewTask(0)
    $definition.RegistrationInfo.Description = 'JARVIS fixed desktop activation, in the signed-in owner session; no password or elevation.'
    $definition.Principal.UserId = $OwnerSid
    $definition.Principal.LogonType = 3 # InteractiveToken, never a stored password.
    $definition.Principal.RunLevel = 0 # Limited user, never SYSTEM/highest.
    $definition.Settings.Enabled = $true
    $definition.Settings.AllowDemandStart = $true
    $definition.Settings.DisallowStartIfOnBatteries = $false
    $definition.Settings.StopIfGoingOnBatteries = $false
    $definition.Settings.ExecutionTimeLimit = 'PT0S'
    $definition.Settings.MultipleInstances = 2 # IgnoreNew, one desktop/model only.
    $action = $definition.Actions.Create(0)
    $action.Path = Join-Path $installRoot 'jarvis-wake-service.exe'
    $action.Arguments = 'desktop'
    $action.WorkingDirectory = $installRoot
    # 6 = create/update, 16 = do not add a broader principal ACE.
    $folder.RegisterTaskDefinition('Launch',$definition,22,$OwnerSid,$null,3,$sddl) | Out-Null
    if (-not $existingService) {
        $credential = New-Object Management.Automation.PSCredential('NT AUTHORITY\LocalService',(New-Object Security.SecureString))
        New-Service -Name $serviceName -DisplayName 'JARVIS Wake' -BinaryPathName ('"'+(Join-Path $installRoot 'jarvis-wake-service.exe')+'" service') -StartupType Automatic -Credential $credential | Out-Null
    }
    Invoke-Sc -Arguments @('config',$serviceName,'start=','delayed-auto','depend=','AudioSrv/AudioEndpointBuilder/Schedule')
    Invoke-Sc -Arguments @('description',$serviceName,'Local Hey Jarvis detector; no cloud, recordings or resident assistant model.')
    # Owner can query/start/stop/pause; cannot change the service image/configuration.
    Invoke-Sc -Arguments @('sdset',$serviceName,"D:(A;;GA;;;SY)(A;;GA;;;BA)(A;;CCLCSWRPWPDTLOCRRC;;;$OwnerSid)")
    Start-Service -Name $serviceName
    $runningPid = (Get-CimInstance Win32_Service -Filter "Name='$serviceName'").ProcessId
    $healthDeadline = [DateTime]::UtcNow.AddSeconds(35)
    $healthy = $false
    while ([DateTime]::UtcNow -lt $healthDeadline) {
        try {
            $health = Get-Content -LiteralPath (Join-Path $statusRoot 'status.json') -Raw | ConvertFrom-Json
            if ($health.pid -eq $runningPid -and $health.phase -in @('listening','no_unlocked_owner','assistant_running')) { $healthy=$true; break }
            if ($health.pid -eq $runningPid -and $health.phase -eq 'failed') { throw "Service initialization failed: $($health.error)" }
        } catch { if ($_.Exception.Message -like 'Service initialization failed:*') { throw } }
        Start-Sleep -Milliseconds 200
    }
    if (-not $healthy) { throw 'Service did not publish a healthy initial state within 35 seconds.' }
    Write-Host "JARVIS Wake installed as LocalService. Status: $statusRoot\status.json"
} catch {
    # Fail closed. A partially updated installation never keeps a live microphone service.
    $failedService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if ($failedService -and $failedService.Status -ne 'Stopped') { Stop-Service -Name $serviceName -Force -ErrorAction Continue }
    Write-Error $_
    exit 1
} finally { Stop-Transcript | Out-Null }

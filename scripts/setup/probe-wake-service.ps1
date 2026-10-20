# Temporary, bounded SCM microphone check. Run elevated; leaves only its JSON report.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'This real Windows service probe requires Windows administrator approval.'
}
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$sourceBinary = Join-Path $projectRoot 'target\wake-service\debug\jarvis-wake-service.exe'
if (-not (Test-Path -LiteralPath $sourceBinary -PathType Leaf)) { throw 'Build jarvis-wake-service first.' }
$serviceName = 'JarvisWakeProbe'
if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) { throw 'Probe service already exists; inspect it first.' }
$binaryDirectory = Join-Path $env:ProgramFiles 'JARVIS\wake-probe'
$reportDirectory = Join-Path $env:ProgramData 'JARVIS\wake-probe'
New-Item -ItemType Directory -Path $binaryDirectory,$reportDirectory -Force | Out-Null
$binary = Join-Path $binaryDirectory 'jarvis-wake-service.exe'
Copy-Item -LiteralPath $sourceBinary -Destination $binary -Force
if ((Get-FileHash -LiteralPath $binary).Hash -ne (Get-FileHash -LiteralPath $sourceBinary).Hash) {
    throw 'Probe copy checksum mismatch.'
}
# Only this newly created report directory: SYSTEM/admin full, LocalService modify.
$acl = New-Object Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true,$false)
foreach ($entry in @(@('S-1-5-18','FullControl'),@('S-1-5-32-544','FullControl'),@('S-1-5-19','Modify'),@('S-1-5-32-545','ReadAndExecute'))) {
    $sid = New-Object Security.Principal.SecurityIdentifier($entry[0])
    $rule = New-Object Security.AccessControl.FileSystemAccessRule($sid,$entry[1],'ContainerInherit,ObjectInherit','None','Allow')
    $acl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $reportDirectory -AclObject $acl
$report = Join-Path $reportDirectory 'report.json'
if (Test-Path -LiteralPath $report) { Remove-Item -LiteralPath $report }
$password = New-Object Security.SecureString
$credential = New-Object Management.Automation.PSCredential('NT AUTHORITY\LocalService',$password)
try {
    New-Service -Name $serviceName -DisplayName 'JARVIS temporary microphone probe' `
        -BinaryPathName ('"' + $binary + '" service-probe') -StartupType Manual -Credential $credential | Out-Null
    Start-Service -Name $serviceName
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    while (-not (Test-Path -LiteralPath $report)) {
        if ([DateTime]::UtcNow -gt $deadline) { throw 'Probe did not publish a report within 20 seconds.' }
        Start-Sleep -Milliseconds 200
    }
    Get-Content -LiteralPath $report -Raw | Write-Output
} finally {
    $probe = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if ($probe -and $probe.Status -ne 'Stopped') { Stop-Service -Name $serviceName -Force }
    if ($probe) {
        & "$env:SystemRoot\System32\sc.exe" delete $serviceName | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Could not remove the temporary probe service.' }
    }
}

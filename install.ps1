# Single product setup: existing JARVIS runtime + user command + native Windows wake service.
[CmdletBinding()]
param([switch]$SkipWakeService, [switch]$SkipBuild, [switch]$RemoveWakeService, [switch]$DefaultWakeMicrophone, [ValidatePattern('^[^"\r\n]{1,120}$')][string]$WakeMicrophone)
$ErrorActionPreference = 'Stop'
if ($DefaultWakeMicrophone -and $WakeMicrophone) { throw 'Choose the Windows default or an explicit microphone, not both.' }
$projectRoot = $PSScriptRoot
if (-not $RemoveWakeService) {
foreach ($relative in @('jarvis.ps1','target\debug\jarvis-core.exe','services\brain\.venv\pyvenv.cfg','services\desktop\.venv\Lib\site-packages\PySide6','models\qwen35-9b-reference\MODEL_MANIFEST.json')) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $relative))) { throw "JARVIS prerequisite missing: $relative. Complete the Brain/Desktop setup first; setup will not download a language model implicitly." }
}
& (Join-Path $projectRoot 'scripts\shell\install-jarvis-command.ps1')
if ($SkipWakeService) { Write-Host 'JARVIS command installed without the wake service.'; return }
& (Join-Path $projectRoot 'scripts\setup\prepare-wake-runtime.ps1') -SkipBuild:$SkipBuild
}
$owner = [Security.Principal.WindowsIdentity]::GetCurrent()
$helper = Join-Path $projectRoot 'scripts\setup\install-wake-service.ps1'
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$arguments = @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$helper+'"'),'-OwnerSid',$owner.User.Value,'-OwnerAccount',('"'+$owner.Name+'"'))
if ($RemoveWakeService) { $arguments += '-Remove' }
if ($WakeMicrophone) { $arguments += @('-Microphone',('"'+$WakeMicrophone+'"')) }
if ($DefaultWakeMicrophone) { $arguments += '-DefaultMicrophone' }
# Actual Windows UAC is required only for protected copies, SCM and the fixed launch task.
$process = Start-Process -FilePath $powershell -ArgumentList $arguments -Verb RunAs -WindowStyle Hidden -PassThru -Wait
if ($process.ExitCode -ne 0) { throw "Windows service setup failed (exit $($process.ExitCode)). See target\wake-install.log." }
if ($RemoveWakeService) { Write-Host 'JARVIS wake service removed; personal data retained.'; return }
Write-Host 'JARVIS service installed. Wake accuracy is experimental; see services\wake\README.md for current test results.'

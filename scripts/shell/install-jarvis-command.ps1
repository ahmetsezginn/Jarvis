[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$commandDirectory = (Resolve-Path -LiteralPath (Join-Path $repositoryRoot 'bin')).Path
if (-not (Test-Path -LiteralPath (Join-Path $commandDirectory 'jarvis.cmd') -PathType Leaf)) {
    throw 'jarvis.cmd bulunamadı.'
}

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$entries = @($userPath -split ';' | Where-Object { $_.Trim() })
$alreadyPresent = @($entries | Where-Object {
    [Environment]::ExpandEnvironmentVariables($_.Trim().Trim('"')).TrimEnd('\') -ieq $commandDirectory.TrimEnd('\')
}).Count -gt 0
if (-not $alreadyPresent) {
    # Preserve the original entries and append only this project's command directory.
    $separator = if ($userPath -and -not $userPath.EndsWith(';')) { ';' } else { '' }
    [Environment]::SetEnvironmentVariable('Path', "$userPath$separator$commandDirectory", 'User')
}
if (-not (@($env:Path -split ';') -contains $commandDirectory)) {
    $env:Path = "$env:Path;$commandDirectory"
}

# Notify Explorer so terminals opened afterward inherit the updated user environment.
# https://learn.microsoft.com/en-us/windows/win32/winmsg/wm-settingchange
if (-not ('JarvisCommand.EnvironmentNotification' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace JarvisCommand {
    public static class EnvironmentNotification {
        [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        public static extern IntPtr SendMessageTimeout(
            IntPtr window, uint message, UIntPtr wParam, string lParam,
            uint flags, uint timeout, out UIntPtr result);
    }
}
'@
}
$notificationResult = [UIntPtr]::Zero
$notified = [JarvisCommand.EnvironmentNotification]::SendMessageTimeout(
    [IntPtr]0xffff, 0x001a, [UIntPtr]::Zero, 'Environment', 2, 3000, [ref]$notificationResult
)
if ($notified -eq [IntPtr]::Zero) {
    Write-Warning 'PATH kaydedildi; ortam bildirimi tamamlanamadı. Gerekirse oturumu yeniden açın.'
}

Write-Host "jarvis komutu kullanıcı PATH'ine eklendi: $commandDirectory"
Write-Host 'Yeni terminalde jarvis yazın. Model GGUF; ONNX devre dışı.'

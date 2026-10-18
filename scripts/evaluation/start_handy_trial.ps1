# Explicit standalone trial. Does not modify JARVIS or open the microphone.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$appPath = Join-Path $projectRoot '.cache\handy-trial\app\handy.exe'
if (-not (Test-Path -LiteralPath $appPath -PathType Leaf)) {
    throw 'Handy trial is not provisioned. See docs/brain/HANDY_TRIAL.md.'
}
$expectedHash = '9a1d2246b64322cb334960a5b3830b0d125070735c355648c498076ec7c0a0ff'
if ((Get-FileHash -LiteralPath $appPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedHash) {
    throw 'Handy trial binary differs from the verified 0.9.8 release.'
}
$storePath = Join-Path (Split-Path -Parent $appPath) 'Data\settings_store.json'
$prefs = (Get-Content -LiteralPath $storePath -Raw | ConvertFrom-Json).settings
if ($prefs.post_process_enabled -or $prefs.always_on_microphone -or $prefs.auto_submit) {
    throw 'Restore offline trial settings: post-processing, always-on microphone and auto-submit OFF.'
}
$previousUpdaterFlag = $env:HANDY_DISABLE_UPDATER
try {
    $env:HANDY_DISABLE_UPDATER = '1'
    Start-Process -FilePath $appPath -WorkingDirectory (Split-Path -Parent $appPath)
} finally {
    if ($null -eq $previousUpdaterFlag) {
        Remove-Item Env:HANDY_DISABLE_UPDATER -ErrorAction SilentlyContinue
    } else {
        $env:HANDY_DISABLE_UPDATER = $previousUpdaterFlag
    }
}
Write-Output 'Handy trial: Ctrl+Alt+Space starts/stops. Text is copied; nothing is submitted.'
Write-Output 'Audio stays in the local portable Data/recordings directory (trial authorization).'

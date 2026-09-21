[CmdletBinding()]
param(
    [switch]$ProcessGuardOnly,
    [switch]$Session
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = (Resolve-Path (Join-Path $repositoryRoot 'services\brain\.venv\Scripts\python.exe')).Path
$ruleName = "JARVIS-M003-offline-$([Guid]::NewGuid())"
$firewallActive = $false
try {
    if ($ProcessGuardOnly) {
        $env:JARVIS_NETWORK_GUARD = 'process'
    } else {
        New-NetFirewallRule -DisplayName $ruleName -Direction Outbound -Action Block -Program $python -ErrorAction Stop | Out-Null
        $activeRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction Stop
        if ($null -eq $activeRule -or $activeRule.Enabled -ne 'True') {
            throw 'The outbound firewall guard was not activated.'
        }
        $firewallActive = $true
        $env:JARVIS_NETWORK_GUARD = 'firewall'
    }
    $env:HF_HUB_OFFLINE = '1'
    $env:TRANSFORMERS_OFFLINE = '1'
    $offlineArguments = @()
    if ($Session) { $offlineArguments = @('--session') }
    & $python -m scripts.tests.offline_e2e @offlineArguments
    if ($LASTEXITCODE -ne 0) { throw 'Offline E2E failed.' }
} finally {
    if ($firewallActive) {
        Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    }
    Remove-Item Env:JARVIS_NETWORK_GUARD -ErrorAction SilentlyContinue
}

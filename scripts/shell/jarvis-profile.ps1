# Load from your PowerShell profile to expose the local JARVIS launcher.
$jarvisRepositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$jarvisLauncherPath = Join-Path $jarvisRepositoryRoot 'jarvis.ps1'
$jarvisCommand = {
    & $jarvisLauncherPath @args
}.GetNewClosure()
Set-Item -Path Function:global:jarvis -Value $jarvisCommand

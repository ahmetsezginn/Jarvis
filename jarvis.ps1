[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Text,

    [switch]$StopCoreOnExit,

    [ValidateSet('gguf')]
    [string]$Model = 'gguf',

    [ValidateSet('qwen35-9b', 'qwen3-4b')]
    [string]$Profile = 'qwen35-9b',

    [switch]$FastRouter
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = $PSScriptRoot
$coreExecutable = Join-Path $repositoryRoot 'target\debug\jarvis-core.exe'
$brainPython = Join-Path $repositoryRoot 'services\brain\.venv\Scripts\python.exe'
$previousBackend = $env:JARVIS_MODEL_BACKEND
$previousProfile = $env:JARVIS_GGUF_PROFILE
$previousPythonPath = $env:PYTHONPATH
if ($Model) { $env:JARVIS_MODEL_BACKEND = $Model }
$env:JARVIS_GGUF_PROFILE = $Profile
$routingArguments = @()
if ($FastRouter) { $routingArguments = @('--fast-router') }
$modelFolder = if ($Profile -eq 'qwen35-9b') { 'qwen35-9b-reference' } else { 'qwen3-4b-gguf' }
$modelManifest = Join-Path $repositoryRoot "models\$modelFolder\MODEL_MANIFEST.json"
$startedCore = $null

function Assert-JarvisPrerequisites {
    if (-not (Test-Path -LiteralPath $coreExecutable -PathType Leaf)) {
        throw "Rust Core not found: $coreExecutable`nRun cargo build --manifest-path .\core\native\Cargo.toml first."
    }
    if (-not (Test-Path -LiteralPath $brainPython -PathType Leaf)) {
        throw "Brain Python environment not found: $brainPython`nComplete the services\brain setup."
    }
    if (-not (Test-Path -LiteralPath $modelManifest -PathType Leaf)) {
        throw "Local Qwen model not found: $modelManifest`nComplete the selected model setup in services\brain\README.md."
    }
}

function Test-JarvisCore {
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $brainPython
    $startInfo.Arguments = '-m jarvis_brain.cli ping'
    $startInfo.WorkingDirectory = $repositoryRoot
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    $pingProcess = New-Object System.Diagnostics.Process
    $pingProcess.StartInfo = $startInfo
    try {
        if (-not $pingProcess.Start()) {
            return $false
        }
        $pingProcess.StandardOutput.ReadToEnd() | Out-Null
        $pingProcess.StandardError.ReadToEnd() | Out-Null
        $pingProcess.WaitForExit()
        return $pingProcess.ExitCode -eq 0
    } finally {
        $pingProcess.Dispose()
    }
}

function Get-ProjectJarvisCoreProcesses {
    $matchingProcesses = @()
    foreach ($process in @(Get-Process -Name 'jarvis-core' -ErrorAction SilentlyContinue)) {
        try {
            if ($process.Path -eq $coreExecutable) {
                $matchingProcesses += $process
            }
        } catch {
            # An inaccessible process is not assumed to belong to this repository.
        }
    }
    return $matchingProcesses
}

function Start-JarvisCore {
    if (Test-JarvisCore) {
        return
    }

    $existingProcesses = @(Get-ProjectJarvisCoreProcesses)
    if ($existingProcesses.Count -gt 0) {
        $processIds = ($existingProcesses.Id -join ', ')
        throw "JARVIS Core is running but its Named Pipe is not responding (PID: $processIds). Stop that process and try again."
    }

    $script:startedCore = Start-Process `
        -FilePath $coreExecutable `
        -ArgumentList 'serve' `
        -WorkingDirectory $repositoryRoot `
        -WindowStyle Hidden `
        -PassThru

    foreach ($attempt in 1..40) {
        Start-Sleep -Milliseconds 250
        if (Test-JarvisCore) {
            return
        }
        if ($script:startedCore.HasExited) {
            throw "Rust Core could not start; exit code: $($script:startedCore.ExitCode)"
        }
    }
    throw 'Rust Core Named Pipe was not ready within 10 seconds.'
}

function Invoke-JarvisText([string]$UserText) {
    & $brainPython -m jarvis_brain.cli ask @routingArguments $UserText
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "JARVIS request failed (exit code $LASTEXITCODE)."
    }
}

try {
    # A missing venv redirector can use its existing base interpreter and installed packages.
    # Never download, replace security settings, or search for arbitrary executables.
    if (-not (Test-Path -LiteralPath $brainPython -PathType Leaf)) {
        $venvConfig = Join-Path $repositoryRoot 'services\brain\.venv\pyvenv.cfg'
        $installedPackages = Join-Path $repositoryRoot 'services\brain\.venv\Lib\site-packages'
        if ((Test-Path -LiteralPath $venvConfig -PathType Leaf) -and
            (Test-Path -LiteralPath $installedPackages -PathType Container)) {
            $baseEntry = Get-Content -LiteralPath $venvConfig | Where-Object { $_ -match '^executable = ' } | Select-Object -First 1
            if ($baseEntry) {
                $baseInterpreter = $baseEntry.Substring('executable = '.Length).Trim()
                if (([IO.Path]::GetFileName($baseInterpreter) -eq 'python.exe') -and
                    (Test-Path -LiteralPath $baseInterpreter -PathType Leaf)) {
                    $brainPython = $baseInterpreter
                    $env:PYTHONPATH = ((Join-Path $repositoryRoot 'services\brain\src'), $installedPackages, $previousPythonPath | Where-Object { $_ }) -join ';'
                    Write-Host 'JARVIS: using the existing base Python interpreter; venv packages retained.'
                }
            }
        }
    }
    Assert-JarvisPrerequisites
    $selectedBackend = 'gguf'
    if ($env:JARVIS_MODEL_BACKEND) { $selectedBackend = $env:JARVIS_MODEL_BACKEND }
    Write-Host "JARVIS model: $selectedBackend/$Profile | Agent loop: ON"
    Start-JarvisCore
    if ($Text) {
        Invoke-JarvisText $Text
        return
    }

    & $brainPython -m jarvis_brain.cli repl @routingArguments
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "JARVIS session failed (exit code $LASTEXITCODE)."
    }
} finally {
    $env:JARVIS_MODEL_BACKEND = $previousBackend
    $env:JARVIS_GGUF_PROFILE = $previousProfile
    $env:PYTHONPATH = $previousPythonPath
    if ($StopCoreOnExit -and $null -ne $startedCore -and -not $startedCore.HasExited) {
        Stop-Process -Id $startedCore.Id
    }
}

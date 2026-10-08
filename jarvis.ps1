[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Text,

    [switch]$StopCoreOnExit,

    [ValidateSet('onnx', 'gguf')]
    [string]$Model,

    [switch]$FastRouter
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = $PSScriptRoot
$coreExecutable = Join-Path $repositoryRoot 'target\debug\jarvis-core.exe'
$brainPython = Join-Path $repositoryRoot 'services\brain\.venv\Scripts\python.exe'
$previousBackend = $env:JARVIS_MODEL_BACKEND
$previousPythonPath = $env:PYTHONPATH
if ($Model) { $env:JARVIS_MODEL_BACKEND = $Model }
$routingArguments = @()
if ($FastRouter) { $routingArguments = @('--fast-router') }
$modelManifest = Join-Path $repositoryRoot 'models\qwen3-0.6b-int4\MODEL_MANIFEST.json'
if ($env:JARVIS_MODEL_BACKEND -eq 'gguf') {
    $modelManifest = Join-Path $repositoryRoot 'models\qwen3-4b-gguf\MODEL_MANIFEST.json'
}
$startedCore = $null

function Assert-JarvisPrerequisites {
    if (-not (Test-Path -LiteralPath $coreExecutable -PathType Leaf)) {
        throw "Rust Core bulunamadı: $coreExecutable`nÖnce cargo build --manifest-path .\core\native\Cargo.toml çalıştırın."
    }
    if (-not (Test-Path -LiteralPath $brainPython -PathType Leaf)) {
        throw "Brain Python ortamı bulunamadı: $brainPython`nservices\brain kurulumunu tamamlayın."
    }
    if (-not (Test-Path -LiteralPath $modelManifest -PathType Leaf)) {
        throw "Yerel Qwen modeli bulunamadı: $modelManifest`nservices\brain\README.md içindeki seçilen modelin kurulumunu tamamlayın."
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
        throw "JARVIS Core süreci çalışıyor fakat Named Pipe yanıt vermiyor (PID: $processIds). Süreci kapatıp yeniden deneyin."
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
            throw "Rust Core başlatılamadı; çıkış kodu: $($script:startedCore.ExitCode)"
        }
    }
    throw 'Rust Core Named Pipe 10 saniye içinde hazır olmadı.'
}

function Invoke-JarvisText([string]$UserText) {
    & $brainPython -m jarvis_brain.cli ask @routingArguments $UserText
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "JARVIS isteği başarısız oldu (çıkış kodu $LASTEXITCODE)."
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
    $selectedBackend = 'onnx'
    if ($env:JARVIS_MODEL_BACKEND) { $selectedBackend = $env:JARVIS_MODEL_BACKEND }
    Write-Host "JARVIS model: $selectedBackend | Sohbet/görev ayrımı: ON"
    Start-JarvisCore
    if ($Text) {
        Invoke-JarvisText $Text
        return
    }

    & $brainPython -m jarvis_brain.cli repl @routingArguments
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "JARVIS oturumu başarısız oldu (çıkış kodu $LASTEXITCODE)."
    }
} finally {
    $env:JARVIS_MODEL_BACKEND = $previousBackend
    $env:PYTHONPATH = $previousPythonPath
    if ($StopCoreOnExit -and $null -ne $startedCore -and -not $startedCore.HasExited) {
        Stop-Process -Id $startedCore.Id
    }
}

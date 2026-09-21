[CmdletBinding()]
param(
    [string]$OutputDirectory,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$modelsRoot = Join-Path $repositoryRoot 'models'
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $modelsRoot 'qwen3-0.6b-int4'
}
$resolvedParent = (Resolve-Path (Split-Path -Parent $OutputDirectory)).Path
if (-not $resolvedParent.StartsWith((Resolve-Path $modelsRoot).Path, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'OutputDirectory must stay under the repository models directory.'
}
$buildEnvironment = Join-Path $PSScriptRoot '.model-build'
$buildPython = Join-Path $buildEnvironment 'Scripts\python.exe'
$bootstrapPython = Join-Path $repositoryRoot 'services\brain\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $bootstrapPython)) {
    $bootstrapPython = (Get-Command python -ErrorAction Stop).Source
}
$sourceDirectory = Join-Path $PSScriptRoot 'source\qwen3-0.6b-pinned'
$cacheDirectory = Join-Path $PSScriptRoot 'cache'
$stagingDirectory = Join-Path $modelsRoot 'qwen3-0.6b-int4.staging'

if ((Test-Path -LiteralPath $OutputDirectory) -and (Get-ChildItem -LiteralPath $OutputDirectory -Force)) {
    if (-not $Force) {
        throw "Artifact already exists at $OutputDirectory. Pass -Force to replace it after a new build succeeds."
    }
}
if (Test-Path -LiteralPath $stagingDirectory) {
    Remove-Item -LiteralPath $stagingDirectory -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $modelsRoot,$cacheDirectory,$stagingDirectory | Out-Null

if (-not (Test-Path -LiteralPath $buildPython)) {
    & $bootstrapPython -c 'import sys; assert sys.version_info >= (3, 12), sys.version'
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12+ is required for model provisioning.' }
    & $bootstrapPython -m venv $buildEnvironment
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the isolated model-build environment.' }
}
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'requirements-build.lock')) {
    & $buildPython -m pip install -r (Join-Path $PSScriptRoot 'requirements-build.lock')
} else {
    & $buildPython -m pip install -r (Join-Path $PSScriptRoot 'requirements-build.in')
}
if ($LASTEXITCODE -ne 0) { throw 'Model-build dependency installation failed.' }

& $buildPython (Join-Path $PSScriptRoot 'download_qwen_source.py') $sourceDirectory
if ($LASTEXITCODE -ne 0) { throw 'Pinned Qwen source download failed.' }

$builderArguments = @(
    '-m', 'onnxruntime_genai.models.builder',
    '-i', $sourceDirectory,
    '-o', $stagingDirectory,
    '-p', 'int4',
    '-e', 'cpu',
    '-c', $cacheDirectory,
    '--extra_options',
    'accuracy_level=4',
    'block_size=32',
    'is_symmetric=true',
    'algo_config=default',
    'hf_token=false'
)
& $buildPython @builderArguments
if ($LASTEXITCODE -ne 0) { throw 'ONNX Runtime GenAI model builder failed.' }

Copy-Item -LiteralPath (Join-Path $sourceDirectory 'LICENSE') -Destination $stagingDirectory
& $buildPython (Join-Path $PSScriptRoot 'verify_qwen3_int4.py') $stagingDirectory --write-manifest
if ($LASTEXITCODE -ne 0) { throw 'Generated model verification failed.' }

if (Test-Path -LiteralPath $OutputDirectory) {
    Remove-Item -LiteralPath $OutputDirectory -Recurse -Force
}
Move-Item -LiteralPath $stagingDirectory -Destination $OutputDirectory
Write-Output "Verified Qwen3-0.6B INT4 CPU artifact: $OutputDirectory"

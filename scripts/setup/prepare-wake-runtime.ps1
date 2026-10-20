# Explicit local setup only. Extract one standalone native DLL, never install/import Python.
[CmdletBinding()]
param([switch]$SkipBuild)
$ErrorActionPreference='Stop'
$projectRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$cache=Join-Path $projectRoot 'target\wake-provider'
$package=Join-Path $projectRoot 'target\wake-package'
$runtime=Join-Path $package 'runtime'
New-Item -ItemType Directory -Path $cache,$runtime -Force | Out-Null
if (-not $SkipBuild) {
    Push-Location $projectRoot
    try { & cargo build -p jarvis-wake-service --release --locked --target-dir target/wake-service -j 2; if ($LASTEXITCODE -ne 0) {throw 'Native wake build failed.'} } finally {Pop-Location}
}
$binary=Join-Path $projectRoot 'target\wake-service\release\jarvis-wake-service.exe'
if (-not (Test-Path -LiteralPath $binary -PathType Leaf)) {throw 'Release wake service binary is missing.'}
Copy-Item -LiteralPath $binary -Destination (Join-Path $package 'jarvis-wake-service.exe') -Force
$pins=[ordered]@{
    'melspectrogram.tflite'='96fa0adccb6e8cf95cb14465409a1a2898ee4a96a85bb9ed3c7eb0e68bf163e8'
    'embedding_model.tflite'='c0aea21eb84a4ce90a08c870da41b7a7173b45269e6a3207c71d67c40f3a59d8'
    'hey_jarvis_v0.1.tflite'='14bff778604985e1b5c19f0f7bbe477a69cf281d8db34b232b3b972411f710e2'
    'libLiteRt.dll'='445f51fed26967fc1112e0de9ddfef7d8497b24322bbfe18b556426a60000891'
}
foreach ($name in @('melspectrogram.tflite','embedding_model.tflite','hey_jarvis_v0.1.tflite')) {
    $download=Join-Path $cache "tflite\$name"
    New-Item -ItemType Directory -Path (Split-Path -Parent $download) -Force | Out-Null
    if (-not (Test-Path -LiteralPath $download -PathType Leaf)) {Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/$name" -OutFile $download}
    if ((Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash.ToLowerInvariant() -ne $pins[$name]) {throw 'Keyword model checksum mismatch.'}
    Copy-Item -LiteralPath $download -Destination (Join-Path $runtime $name) -Force
}
$wheel=Join-Path $cache 'ai_edge_litert-2.3.0-cp311-cp311-win_amd64.whl'
if (-not (Test-Path -LiteralPath $wheel -PathType Leaf)) {Invoke-WebRequest -UseBasicParsing -Uri 'https://files.pythonhosted.org/packages/d5/32/aa64f8c83e8b72e3929570c9859498146ddcce560de01d23d7bada99295c/ai_edge_litert-2.3.0-cp311-cp311-win_amd64.whl' -OutFile $wheel}
if ((Get-FileHash -LiteralPath $wheel -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'ffee5993b859580650e844fce322e93b7abf50dfa36fd0fcbde41e079d1eebe3') {throw 'Official LiteRT package checksum mismatch.'}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip=[IO.Compression.ZipFile]::OpenRead($wheel)
try {
    [IO.Compression.ZipFileExtensions]::ExtractToFile($zip.GetEntry('ai_edge_litert/libLiteRt.dll'),(Join-Path $runtime 'libLiteRt.dll'),$true)
} finally {$zip.Dispose()}
if ((Get-FileHash -LiteralPath (Join-Path $runtime 'libLiteRt.dll') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $pins['libLiteRt.dll']) {throw 'Native LiteRT checksum mismatch.'}
foreach ($name in @('LICENSE.openwakeword-code','LICENSE.openwakeword-models','THIRD_PARTY.md')) {Copy-Item -LiteralPath (Join-Path $projectRoot "services\wake\resources\$name") -Destination (Join-Path $runtime $name) -Force}
$utf8=New-Object Text.UTF8Encoding($false)
[IO.File]::WriteAllText((Join-Path $runtime 'manifest.json'),($pins | ConvertTo-Json),$utf8)
[IO.File]::WriteAllText((Join-Path $package 'provider.json'),(@{schema=1;provider='openwakeword-litert-cpu';model_release='v0.5.1';litert='2.3.0';threshold=0.5;recordings=$false} | ConvertTo-Json),$utf8)
Write-Host "Prepared native CPU wake package: $package"

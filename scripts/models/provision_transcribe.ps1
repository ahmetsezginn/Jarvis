# Explicit Windows setup. No runtime downloads, ONNX DLLs, microphone or Handy GUI.
[CmdletBinding()]
param([string]$HandyDirectory)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$prefix = Join-Path $projectRoot 'models\transcribe-runtime'
if (-not $HandyDirectory) {
    $HandyDirectory = Join-Path $projectRoot '.cache\handy-trial\app'
}
if (-not (Test-Path -LiteralPath (Join-Path $HandyDirectory 'transcribe.dll'))) {
    $setupRoot = Join-Path $projectRoot '.cache\transcribe-provision'
    New-Item -ItemType Directory -Force -Path $setupRoot | Out-Null
    $installer = Join-Path $setupRoot 'Handy_0.9.8_x64-setup.exe'
    Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/cjpais/Handy/releases/download/v0.9.8/Handy_0.9.8_x64-setup.exe' -OutFile $installer
    $expected = '4212edb5658ec2867855fc2ee83ac16ec5bbad09db3c2da8d3d9d5f8bd5eeccc'
    if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
        throw 'Handy 0.9.8 installer checksum mismatch.'
    }
    $HandyDirectory = Join-Path $setupRoot 'app'
    $process = Start-Process -FilePath $installer -ArgumentList ('/S /PORTABLE /D=' + $HandyDirectory) -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw 'Native provider extraction failed.' }
}
$signature = Get-AuthenticodeSignature -LiteralPath (Join-Path $HandyDirectory 'transcribe.dll')
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=YNYNG LLC') {
    throw 'Expected signed official Handy native provider.'
}
$tools = Get-ChildItem 'C:\Program Files\Microsoft Visual Studio' -Recurse -Filter 'lib.exe' |
    Where-Object { $_.FullName -match '\\Hostx64\\x64\\lib.exe$' } |
    Sort-Object FullName -Descending | Select-Object -First 1
if (-not $tools) { throw 'Visual Studio x64 C++ build tools are required.' }
$dumpbin = Join-Path $tools.DirectoryName 'dumpbin.exe'
$exports = & $dumpbin /nologo /exports (Join-Path $HandyDirectory 'transcribe.dll')
if ($LASTEXITCODE) { throw 'Cannot inspect provider exports.' }
$names = @($exports | ForEach-Object {
    if ($_ -match '^\s+\d+\s+[0-9A-F]+\s+[0-9A-F]+\s+(transcribe_[A-Za-z0-9_]+)\s*$') { $Matches[1] }
})
if ($names.Count -lt 40 -or 'transcribe_version' -notin $names) { throw 'Unexpected provider exports.' }
$binDir = Join-Path $prefix 'bin'
$libDir = Join-Path $prefix 'lib'
New-Item -ItemType Directory -Force -Path $binDir,$libDir | Out-Null
# The official package uses one C ABI DLL; create its MSVC import library from exports.
$defPath = Join-Path $libDir 'transcribe.def'
[IO.File]::WriteAllLines($defPath, @('LIBRARY transcribe.dll', 'EXPORTS') + $names, [Text.Encoding]::ASCII)
& $tools.FullName /nologo /machine:x64 "/def:$defPath" "/out:$(Join-Path $libDir 'transcribe.lib')"
if ($LASTEXITCODE) { throw 'Cannot create provider import library.' }
$expectedPins = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'transcribe-runtime-pins.json') -Raw | ConvertFrom-Json
$runtimeFiles = @($expectedPins.files.PSObject.Properties | ForEach-Object {
    $file = Get-Item -LiteralPath (Join-Path $HandyDirectory $_.Name)
    if ((Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -ne $_.Value) {
        throw ('Native provider checksum mismatch: ' + $_.Name)
    }
    $file
})
foreach ($file in $runtimeFiles) { Copy-Item -LiteralPath $file.FullName -Destination $binDir -Force }
$manifest = @{ shared=$true; libraries=@('transcribe'); lib_dir='lib'; module_dir='bin' }
[IO.File]::WriteAllText((Join-Path $libDir 'transcribe-link.json'), ($manifest | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
$pins = @{}
foreach ($file in $runtimeFiles) { $pins[$file.Name]=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
$provenance = @{ handy='0.9.8'; transcribe_cpp='0.2.4'; source='https://github.com/cjpais/Handy/releases/tag/v0.9.8'; files=$pins }
[IO.File]::WriteAllText((Join-Path $prefix 'PROVENANCE.json'), ($provenance | ConvertTo-Json -Depth 4), [Text.UTF8Encoding]::new($false))
Write-Output "Provisioned native transcribe.cpp 0.2.4 CPU/Vulkan at $prefix (no ONNX)."

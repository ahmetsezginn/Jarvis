[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$taskPackages = Join-Path $taskRoot 'services\desktop\.venv\Lib\site-packages'
$taskPreviousCmake = $env:CMAKE
$taskPreviousClang = $env:LIBCLANG_PATH
$taskPreviousFlags = $env:CXXFLAGS
try {
    $env:CMAKE = Join-Path $taskPackages 'cmake\data\bin\cmake.exe'
    $env:LIBCLANG_PATH = Join-Path $taskPackages 'clang\native'
    $env:CXXFLAGS = '/O2'
    if (-not (Test-Path -LiteralPath $env:CMAKE)) { throw 'Install desktop requirements-build.txt first.' }
    cargo build --manifest-path (Join-Path $taskRoot 'core\native\Cargo.toml') -j 2
    if ($LASTEXITCODE -ne 0) { throw 'Native voice build failed.' }
} finally {
    $env:CMAKE = $taskPreviousCmake
    $env:LIBCLANG_PATH = $taskPreviousClang
    $env:CXXFLAGS = $taskPreviousFlags
}

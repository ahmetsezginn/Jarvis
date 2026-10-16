# Opt-in local GUI smoke test: synthetic files only, no personal CV contents.
[CmdletBinding()]
param([switch]$RestoreCore)
$ErrorActionPreference = 'Stop'
$taskRepository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$taskExecutable = Join-Path $taskRepository 'target\debug\jarvis-core.exe'
$taskPythonConfig = Join-Path $taskRepository 'services\brain\.venv\pyvenv.cfg'
$taskPythonEntry = Get-Content -LiteralPath $taskPythonConfig | Where-Object { $_ -match '^executable = ' } | Select-Object -First 1
$taskPython = $taskPythonEntry.Substring('executable = '.Length).Trim()
if (-not (Test-Path -LiteralPath $taskPython -PathType Leaf)) { throw 'Configured Python is unavailable' }
if (@(Get-Process -Name jarvis-core -ErrorAction SilentlyContinue).Count -gt 0) {
    throw 'A Core is already running. Stop the project Core before running the isolated fixture test.'
}
$taskFixture = Join-Path $taskRepository 'target\file-context-live'
$taskPortfolio = Join-Path $taskFixture 'cvfolder\portfolio'
New-Item -ItemType Directory -Path $taskPortfolio -Force | Out-Null
# Generate a valid blank one-page PDF, including byte offsets and cross-reference table.
$taskPdf = "%PDF-1.4`n"
$taskOffsets = @()
$taskObjects = @('<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R] /Count 1 >>', '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Resources << >> /Contents 4 0 R >>', "<< /Length 0 >>`nstream`nendstream")
for ($taskIndex = 0; $taskIndex -lt $taskObjects.Count; $taskIndex++) {
    $taskOffsets += [Text.Encoding]::ASCII.GetByteCount($taskPdf)
    $taskPdf += "$($taskIndex + 1) 0 obj`n$($taskObjects[$taskIndex])`nendobj`n"
}
$taskXref = [Text.Encoding]::ASCII.GetByteCount($taskPdf)
$taskPdf += "xref`n0 5`n0000000000 65535 f `n"
foreach ($taskOffset in $taskOffsets) { $taskPdf += ('{0:D10} 00000 n ' -f $taskOffset) + "`n" }
$taskPdf += "trailer`n<< /Size 5 /Root 1 0 R >>`nstartxref`n$taskXref`n%%EOF`n"
foreach ($taskName in @('Ahmet-Sezgin-CV-EN.pdf', 'Ahmet-Sezgin-CV-TR.pdf', 'Ahmet_Sezgin_CV.pdf', 'CV-Grafik-tr.pdf.pdf', 'CV-tr.pdf', 'CV.pdf', 'Grey Clean CV Resume Photo_TR.pdf.pdf')) {
    [IO.File]::WriteAllBytes((Join-Path $taskPortfolio $taskName), [Text.Encoding]::ASCII.GetBytes($taskPdf))
}
[IO.File]::WriteAllBytes((Join-Path $taskFixture 'CV-tr.pdf'), [Text.Encoding]::ASCII.GetBytes($taskPdf))
[IO.File]::WriteAllText((Join-Path $taskFixture 'Toplantı-Sunum.txt'), 'Synthetic metadata-search fixture.', [Text.Encoding]::UTF8)
$taskDesktop = Join-Path $taskRepository 'target\file-context-desktop-live'
$taskNested = Join-Path $taskDesktop 'Proje'
New-Item -ItemType Directory -Path $taskNested -Force | Out-Null
[IO.File]::WriteAllText((Join-Path $taskDesktop 'New Metin Belgesi.txt'), 'Synthetic root note.', [Text.Encoding]::UTF8)
[IO.File]::WriteAllText((Join-Path $taskNested 'uretim-notu.txt'), 'Synthetic nested note.', [Text.Encoding]::UTF8)
$taskFilesConfig = Join-Path $taskRepository 'target\file-context-live.local.toml'
$taskConfigText = "[[roots]]`nname = `"Downloads`"`npath = '$taskFixture'`n"
$taskConfigText += "`n[[roots]]`nname = `"Desktop`"`npath = '$taskDesktop'`n"
[IO.File]::WriteAllText($taskFilesConfig, $taskConfigText, (New-Object Text.UTF8Encoding($false)))
$taskOldFilesConfig = $env:JARVIS_FILES_CONFIG
$taskOldPythonPath = $env:PYTHONPATH
$taskOldLiveFlag = $env:JARVIS_RUN_FILE_CONTEXT_LIVE
$taskCore = $null
try {
    $env:JARVIS_FILES_CONFIG = $taskFilesConfig
    $env:PYTHONPATH = ((Join-Path $taskRepository 'services\brain\src'), (Join-Path $taskRepository 'services\brain\.venv\Lib\site-packages')) -join ';'
    $env:JARVIS_RUN_FILE_CONTEXT_LIVE = '1'
    $taskCore = Start-Process -FilePath $taskExecutable -ArgumentList 'serve' -WorkingDirectory $taskRepository -WindowStyle Hidden -PassThru
    $taskReady = $false
    foreach ($taskAttempt in 1..40) {
        & $taskPython -m jarvis_brain.cli ping 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $taskReady = $true; break }
        if ($taskCore.HasExited) { throw 'Fixture Core exited during startup' }
        Start-Sleep -Milliseconds 250
    }
    if (-not $taskReady) { throw 'Fixture Core did not become ready' }
    $taskReport = Join-Path $taskRepository 'target\assistant-analysis\live-final.xml'
    & $taskPython -m pytest (Join-Path $taskRepository 'services\brain\tests\integration\test_live_agent.py') -o 'addopts=' -q -s --tb=short --junitxml $taskReport
    if ($LASTEXITCODE -ne 0) { throw 'Live file-context test failed' }
} finally {
    if ($null -ne $taskCore -and -not $taskCore.HasExited -and $taskCore.Path -eq $taskExecutable) {
        $taskCore.Kill()
        $taskCore.WaitForExit(5000) | Out-Null
    }
    $env:JARVIS_FILES_CONFIG = $taskOldFilesConfig
    $env:PYTHONPATH = $taskOldPythonPath
    $env:JARVIS_RUN_FILE_CONTEXT_LIVE = $taskOldLiveFlag
    if ($RestoreCore) {
        Start-Process -FilePath $taskExecutable -ArgumentList 'serve' -WorkingDirectory $taskRepository -WindowStyle Hidden | Out-Null
    }
}

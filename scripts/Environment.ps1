$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Get-ProjectPython {
    $candidates = @((Join-Path $ProjectRoot 'backend\.venv\Scripts\python.exe'))
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        $resolvedPython = & $launcher.Source -3.13 -c 'import sys; print(sys.executable)'
        if ($LASTEXITCODE -eq 0) { return $resolvedPython }
    }
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notlike '*WindowsApps*') {
        & $pythonCommand.Source -c 'import sys; assert sys.version_info[:2] == (3, 13)'
        if ($LASTEXITCODE -eq 0) { return $pythonCommand.Source }
    }
    $embedded = Join-Path $ProjectRoot '.tools\python\python.exe'
    if (Test-Path -LiteralPath $embedded) { return $embedded }
    throw 'Instale Python 3.13 ou disponibilize backend\.venv. Consulte README.md.'
}

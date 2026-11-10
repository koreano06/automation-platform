param([switch]$Browser, [switch]$Desktop)
. "$PSScriptRoot\Environment.ps1"
$pythonPath = Get-ProjectPython
if ($Desktop) {
    & $pythonPath -c 'import tkinter'
    if ($LASTEXITCODE -ne 0) { throw 'Desktop precisa do Python 3.13 completo com Tkinter. Crie backend\.venv com essa instalação e repita Setup.ps1 -Desktop.' }
}
$venvPath = Join-Path $ProjectRoot 'backend\.venv'
if (-not (Test-Path -LiteralPath $venvPath) -and $pythonPath -notlike '*\.tools\*') {
    & $pythonPath -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar o ambiente virtual.' }
    $pythonPath = Join-Path $venvPath 'Scripts\python.exe'
}
$extras = @('dev')
if ($Browser) { $extras += 'runner' }
if ($Desktop) { $extras += 'desktop' }
Push-Location $ProjectRoot
try {
    & $pythonPath -m pip install setuptools wheel --disable-pip-version-check
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar dependências.' }
    $package = 'backend[' + ($extras -join ',') + ']'
    & $pythonPath -m pip install --no-build-isolation -c backend/requirements.lock -e $package
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar backend.' }
    if ($Browser) {
        & $pythonPath -m playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar Chromium.' }
    }
    & $pythonPath -m app.cli migrate
    if ($LASTEXITCODE -ne 0) { throw 'Falha nas migrações. O banco pode exigir intervenção.' }
    Push-Location frontend
    try {
        & npm.cmd ci --no-fund --no-audit
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar frontend.' }
    } finally { Pop-Location }
    Write-Host 'Preparação concluída. Crie o administrador: .\scripts\Manage.ps1 create-admin'
} finally { Pop-Location }

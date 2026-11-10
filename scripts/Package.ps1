. "$PSScriptRoot\Environment.ps1"
$pythonPath = Get-ProjectPython
Push-Location $ProjectRoot
try {
    & $pythonPath "$PSScriptRoot\package_release.py"
    if ($LASTEXITCODE -ne 0) { throw 'A criação do pacote não foi concluída.' }
} finally { Pop-Location }

param(
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet('migrate','create-admin','reset-password','seed-demo','backup')]
    [string]$Command,
    [string]$Username = 'admin'
)
. "$PSScriptRoot\Environment.ps1"
$pythonPath = Get-ProjectPython
Push-Location $ProjectRoot
try {
    & $pythonPath -m app.cli $Command --username $Username
    if ($LASTEXITCODE -ne 0) { throw 'O comando não foi concluído.' }
} finally { Pop-Location }

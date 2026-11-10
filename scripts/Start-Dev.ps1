 . "$PSScriptRoot\Environment.ps1"
$pythonPath = Get-ProjectPython
$nodePath = (Get-Command node -ErrorAction Stop).Source
$runtimeDirectory = Join-Path $ProjectRoot 'data'
New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
$stateFile = Join-Path $runtimeDirectory 'dev-processes.json'
if (Test-Path -LiteralPath $stateFile) {
    throw 'Já existe um registro de processos. Use Restart-Dev.ps1 para atualizar e reiniciar.'
}
$occupied = @(Get-NetTCPConnection -State Listen -LocalPort 8000,5173 -ErrorAction SilentlyContinue)
if ($occupied.Count -gt 0) { throw 'As portas 8000 ou 5173 já estão em uso. Encerre os serviços antigos antes de iniciar; o banco não foi alterado.' }
Push-Location $ProjectRoot
try {
    & $pythonPath -m app.cli migrate
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao atualizar o banco; os serviços não foram iniciados.' }
} finally { Pop-Location }
$processes = @()
try {
    $definitions = @(
        @{ Name='api'; File=$pythonPath; Directory=(Join-Path $ProjectRoot 'backend'); Arguments=@('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') },
        @{ Name='worker'; File=$pythonPath; Directory=(Join-Path $ProjectRoot 'backend'); Arguments=@('-m','app.worker') },
        @{ Name='frontend'; File=$nodePath; Directory=(Join-Path $ProjectRoot 'frontend'); Arguments=@(('"' + (Join-Path $ProjectRoot 'frontend\node_modules\vite\bin\vite.js') + '"'),'--host','127.0.0.1') }
    )
    foreach ($definition in $definitions) {
        $process = Start-Process -FilePath $definition.File -ArgumentList $definition.Arguments -WorkingDirectory $definition.Directory -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDirectory ($definition.Name + '.log')) -RedirectStandardError (Join-Path $runtimeDirectory ($definition.Name + '.error.log'))
        $processes += @{ Name=$definition.Name; Id=$process.Id; Started=$process.StartTime.ToUniversalTime().ToString('o') }
    }
    $processes | ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding UTF8
    Start-Sleep -Seconds 2
    foreach ($item in $processes) {
        if (-not (Get-Process -Id $item.Id -ErrorAction SilentlyContinue)) { throw ('Processo encerrou: ' + $item.Name + '. Consulte data/*.error.log.') }
    }
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 10
    if ($health.status -ne 'ok') { throw 'A API não confirmou o início.' }
    $contract = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/openapi.json' -TimeoutSec 10
    if (-not $contract.paths.'/platforms/{platform_id}'.delete) { throw 'A API em execução está desatualizada: rota de exclusão ausente.' }
    Write-Host 'Workspace: http://127.0.0.1:5173'
    Write-Host 'API: http://127.0.0.1:8000/docs'
    Write-Host 'Para encerrar: .\scripts\Stop-Dev.ps1'
} catch {
    foreach ($item in $processes) {
        $owned = Get-Process -Id $item.Id -ErrorAction SilentlyContinue
        if ($owned -and $owned.StartTime.ToUniversalTime().ToString('o') -eq $item.Started) { Stop-Process -Id $item.Id }
    }
    if (Test-Path -LiteralPath $stateFile) { Remove-Item -LiteralPath $stateFile }
    throw
}

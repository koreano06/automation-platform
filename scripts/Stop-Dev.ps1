 . "$PSScriptRoot\Environment.ps1"
$stateFile = Join-Path $ProjectRoot 'data\dev-processes.json'
if (-not (Test-Path -LiteralPath $stateFile)) { Write-Host 'Nenhum processo registrado.'; exit 0 }
$processes = Get-Content -Raw -LiteralPath $stateFile | ConvertFrom-Json
foreach ($item in $processes) {
    $owned = Get-Process -Id $item.Id -ErrorAction SilentlyContinue
    if ($owned -and $owned.StartTime.ToUniversalTime().ToString('o') -eq $item.Started) {
        Stop-Process -Id $item.Id
        Write-Host ('Encerrado: ' + $item.Name)
    }
}
Remove-Item -LiteralPath $stateFile

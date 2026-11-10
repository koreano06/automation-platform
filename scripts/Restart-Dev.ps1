. "$PSScriptRoot\Environment.ps1"
try {
    & "$PSScriptRoot\Stop-Dev.ps1"
} catch {
    throw 'O Windows não permitiu encerrar os serviços atuais. Execute Restart-Dev.ps1 no PowerShell como administrador ou encerre os serviços no terminal que os iniciou. A migração não foi aplicada.'
}
& "$PSScriptRoot\Start-Dev.ps1"

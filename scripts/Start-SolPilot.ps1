. "$PSScriptRoot\Environment.ps1"
$securePassword = Read-Host 'Senha do SOL (não será gravada em arquivo)' -AsSecureString
$pointer = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
$previousPassword = [Environment]::GetEnvironmentVariable('AUTOMATION_SECRET_SOL_PASSWORD', 'Process')
$previousEnabled = [Environment]::GetEnvironmentVariable('LOCAL_RUNNER_ENABLED', 'Process')
$previousHeadless = [Environment]::GetEnvironmentVariable('BROWSER_HEADLESS', 'Process')
$previousHosts = [Environment]::GetEnvironmentVariable('LOCAL_ALLOWED_HOSTS', 'Process')
try {
    $env:AUTOMATION_SECRET_SOL_PASSWORD = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $env:LOCAL_RUNNER_ENABLED = 'true'
    $env:BROWSER_HEADLESS = 'false'
    $env:LOCAL_ALLOWED_HOSTS = '["sol.pucgoias.edu.br"]'
    Write-Host 'O worker receberá a credencial somente no ambiente do processo. Configure os seletores do piloto antes de enfileirar.'
    & "$PSScriptRoot\Restart-Dev.ps1"
} finally {
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    [Environment]::SetEnvironmentVariable('AUTOMATION_SECRET_SOL_PASSWORD', $previousPassword, 'Process')
    [Environment]::SetEnvironmentVariable('LOCAL_RUNNER_ENABLED', $previousEnabled, 'Process')
    [Environment]::SetEnvironmentVariable('BROWSER_HEADLESS', $previousHeadless, 'Process')
    [Environment]::SetEnvironmentVariable('LOCAL_ALLOWED_HOSTS', $previousHosts, 'Process')
}

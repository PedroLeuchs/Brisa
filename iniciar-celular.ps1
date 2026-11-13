param([string]$ConfigDirectory = (Join-Path $PSScriptRoot 'data\mobile-tls'))

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$configPath = Join-Path $ConfigDirectory 'config.json'
$certificatePath = Join-Path $ConfigDirectory 'brisa-server.crt'
$keyPath = Join-Path $ConfigDirectory 'brisa-server.key'
foreach ($required in @($configPath, $certificatePath, $keyPath)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw 'Execute preparar-celular.ps1 antes de iniciar o acesso HTTPS.'
    }
}
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$address = [string]$config.address
$port = [int]$config.port
$python = (Resolve-Path (Join-Path $PSScriptRoot '.venv\Scripts\python.exe')).Path
$runtime = (& $python -c 'import sys; print(sys._base_executable)').Trim()

$otherBrisa = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -eq 8080 }
if ($otherBrisa) {
    throw 'O Brisa local ainda esta ativo na porta 8080. Encerre essa janela/processo primeiro para manter somente um worker de automacoes.'
}

$validFirewallRule = $false
$firewallRules = Get-NetFirewallRule -DisplayName 'Brisa HTTPS local' -ErrorAction SilentlyContinue |
    Where-Object { $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow' }
foreach ($rule in $firewallRules) {
    $rulePort = $rule | Get-NetFirewallPortFilter
    $ruleAddress = $rule | Get-NetFirewallAddressFilter
    $ruleApplication = $rule | Get-NetFirewallApplicationFilter
    if ($rulePort.Protocol -eq 'TCP' -and $rulePort.LocalPort -eq $port -and
        $ruleAddress.LocalAddress -contains $address -and $ruleAddress.RemoteAddress -contains 'LocalSubnet' -and
        $ruleApplication.Program -and
        $ruleApplication.Program.Trim().ToLowerInvariant() -eq $runtime.ToLowerInvariant()) {
        $validFirewallRule = $true
    }
}
if (-not $validFirewallRule) {
    throw 'A regra restrita do firewall ainda nao foi criada. Execute configurar-firewall-celular.ps1 como administrador.'
}
$broadRule = $false
foreach ($candidate in (Get-NetFirewallApplicationFilter -Program $runtime -ErrorAction SilentlyContinue |
        Get-NetFirewallRule -ErrorAction SilentlyContinue |
        Where-Object { $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow' })) {
    $candidatePort = $candidate | Get-NetFirewallPortFilter
    $candidateAddress = $candidate | Get-NetFirewallAddressFilter
    if ($candidatePort.Protocol -eq 'TCP' -and
        ($candidatePort.LocalPort -contains 'Any' -or $candidateAddress.RemoteAddress -contains 'Any')) {
        $broadRule = $true
    }
}
if ($broadRule) { throw 'Existe uma regra TCP ampla para o runtime do Brisa; ajuste o firewall antes de iniciar.' }

$hosts = @('localhost', '127.0.0.1', $address) | Select-Object -Unique
$env:ALLOWED_HOSTS = $hosts -join ','
$env:COOKIE_SECURE = 'true'
Write-Host "Brisa HTTPS: https://${address}:$port"
Write-Host 'Mantenha esta janela aberta. Ctrl+C encerra o acesso.'
& $python -m uvicorn app:app --host $address --port $port --workers 1 --no-access-log --no-proxy-headers --ssl-certfile $certificatePath --ssl-keyfile $keyPath

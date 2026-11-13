param([switch]$Remove)

$ErrorActionPreference = 'Stop'
$ruleName = 'Brisa HTTPS local'
$configPath = Join-Path $PSScriptRoot 'data\mobile-tls\config.json'
$statePath = Join-Path $PSScriptRoot 'data\mobile-tls\firewall-state.json'
if (-not (Test-Path -LiteralPath $configPath)) { throw 'Execute preparar-celular.ps1 primeiro.' }
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Abra o PowerShell como administrador para alterar somente a regra do Brisa.'
}

Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
if ($Remove) {
    if (Test-Path -LiteralPath $statePath) {
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        foreach ($name in @($state.disabled_rules)) {
            Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue | Enable-NetFirewallRule
        }
        Remove-Item -LiteralPath $statePath -Force
    }
    Write-Host 'Regra Brisa HTTPS local removida.'
    exit 0
}

$address = [string]$config.address
$port = [int]$config.port
$python = (Resolve-Path (Join-Path $PSScriptRoot '.venv\Scripts\python.exe')).Path
$runtime = (& $python -c 'import sys; print(sys._base_executable)').Trim()
$broadRules = @()
foreach ($candidate in (Get-NetFirewallApplicationFilter -Program $runtime -ErrorAction SilentlyContinue |
        Get-NetFirewallRule -ErrorAction SilentlyContinue |
        Where-Object { $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow' })) {
    $portFilter = $candidate | Get-NetFirewallPortFilter
    $addressFilter = $candidate | Get-NetFirewallAddressFilter
    if ($portFilter.Protocol -eq 'TCP' -and
        ($portFilter.LocalPort -contains 'Any' -or $addressFilter.RemoteAddress -contains 'Any')) {
        $broadRules += $candidate
    }
}
if ($broadRules.Count -gt 0) {
    @{ disabled_rules = @($broadRules | ForEach-Object { $_.Name }) } |
        ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding utf8
    $broadRules | Disable-NetFirewallRule
}
New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Enabled True `
    -Profile Private,Public -Protocol TCP -LocalAddress $address -LocalPort $port `
    -RemoteAddress LocalSubnet -Program $runtime | Out-Null
Write-Host "Firewall liberado somente para TCP $address`:$port, origem LocalSubnet e executavel do ambiente Brisa."
if ($broadRules.Count -gt 0) { Write-Host 'Uma regra TCP ampla do mesmo runtime foi desativada e registrada para reversao.' }
Write-Host 'A regra pode ser removida com: .\configurar-firewall-celular.ps1 -Remove'

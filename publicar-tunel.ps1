$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'A ativacao unica do Funnel exige um PowerShell como Administrador.'
}
$tailscale = Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
$state = (& $tailscale status --json | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0 -or $state.BackendState -ne 'Running') { throw 'Entre no Tailscale antes de publicar.' }
$dnsName = ([string]$state.Self.DNSName).TrimEnd('.')
if ($dnsName -notmatch '^[a-zA-Z0-9.-]+\.ts\.net$') { throw 'Hostname Tailscale invalido.' }
$token = (Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'data\vercel-proxy.token')).Trim()
if ($token.Length -lt 32) { throw 'Token local invalido.' }
try {
    Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8080/api/session' -Headers @{'X-Brisa-Proxy-Token'=$token} -TimeoutSec 5 | Out-Null
    throw 'A API nao exigiu login; publicacao interrompida.'
} catch {
    if (-not $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 401) {
        throw 'O backend deve responder 401 sem sessao e com token correto. Inicie a nova versao antes de publicar.'
    }
}
try {
    Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8080/api/session' -TimeoutSec 5 | Out-Null
    throw 'A API nao exigiu o segredo do proxy.'
} catch {
    if (-not $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 403) {
        throw 'A API deve recusar pedidos sem token antes da publicacao.'
    }
}
$configText = (& $tailscale serve status --json) -join "`n"
if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel conferir os servicos Tailscale existentes.' }
$config = $configText | ConvertFrom-Json
if ($config.Web) {
    foreach ($entry in $config.Web.PSObject.Properties) {
        if ($entry.Name -ne "${dnsName}:443") { throw 'Ha outro servico publicado. Revise a configuracao Tailscale manualmente.' }
        foreach ($handler in $entry.Value.Handlers.PSObject.Properties) {
            if ($handler.Name -ne '/' -or $handler.Value.Proxy -ne 'http://127.0.0.1:8080') {
                throw 'A configuracao atual aponta para outro destino. Revise-a antes de publicar.'
            }
        }
    }
}
$backup = Join-Path $PSScriptRoot 'data\tailscale-before-funnel.json'
if (-not (Test-Path $backup)) { [IO.File]::WriteAllText($backup, $configText) }
& $tailscale funnel --bg --https=443 http://127.0.0.1:8080
if ($LASTEXITCODE -ne 0) { throw 'Funnel nao ativado. Confira a autorizacao exibida pelo Tailscale.' }
$token = $null
Write-Host "Tunel configurado: https://$dnsName"
Write-Host 'Use esse endereco em BRISA_BACKEND_URL na Vercel. As APIs continuam exigindo token do proxy e login do usuario.'

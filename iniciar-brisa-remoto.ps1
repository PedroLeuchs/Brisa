$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$mutex = New-Object System.Threading.Mutex($false, 'Global\BrisaHomeRunner')
$held = $false
try {
    $held = $mutex.WaitOne(0)
    if (-not $held) { throw 'Ja existe uma instancia do iniciador Brisa.' }
    if (Get-NetTCPConnection -State Listen -LocalPort 8080,8443 -ErrorAction SilentlyContinue) {
        throw 'Uma porta do Brisa (8080/8443) ja esta ocupada. Encerre o iniciador anterior de forma coordenada; nenhum processo foi encerrado automaticamente.'
    }
    $runningBrisa = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='uvicorn.exe'" | Where-Object {
        $_.CommandLine -match '\buvicorn\b.+\bapp:app\b' -and
        ($_.ExecutablePath -like "$PSScriptRoot\*" -or $_.CommandLine -like "*$PSScriptRoot*")
    }
    if ($runningBrisa) {
        throw 'Outro servidor deste projeto ja esta ativo. Coordene a troca para preservar um unico executor.'
    }
    $tailscale = Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
    if (-not (Test-Path $tailscale)) { throw 'Tailscale nao encontrado.' }
    $state = (& $tailscale status --json | ConvertFrom-Json)
    if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel consultar Tailscale.' }
    $dnsName = ([string]$state.Self.DNSName).TrimEnd('.')
    if ($dnsName -notmatch '^[a-zA-Z0-9.-]+\.ts\.net$') { throw 'Entre no Tailscale antes de iniciar.' }
    $tokenPath = Join-Path $PSScriptRoot 'data\vercel-proxy.token'
    $env:BRISA_PROXY_TOKEN = (Get-Content -Raw -LiteralPath $tokenPath).Trim()
    if ($env:BRISA_PROXY_TOKEN.Length -lt 32) { throw 'Configure o token privado primeiro.' }
    $env:TUYA_TRANSPORT = 'local'
    $env:COOKIE_SECURE = 'true'
    $env:ALLOWED_HOSTS = "localhost,127.0.0.1,$dnsName"
    & "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8080 --workers 1 --no-access-log --no-proxy-headers
    if ($LASTEXITCODE -ne 0) { throw 'O backend Brisa encerrou com erro.' }
} finally {
    Remove-Item Env:BRISA_PROXY_TOKEN -ErrorAction SilentlyContinue
    if ($held) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}

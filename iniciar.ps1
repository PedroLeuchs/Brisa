param([switch]$Lan, [string]$CertFile, [string]$KeyFile)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$arBind = if ($Lan) { '0.0.0.0' } else { '127.0.0.1' }
$arTls = @()
if ($CertFile -or $KeyFile) {
    if (-not ($CertFile -and $KeyFile)) { throw 'Informe CertFile e KeyFile juntos.' }
    if (-not (Test-Path -LiteralPath $CertFile) -or -not (Test-Path -LiteralPath $KeyFile)) { throw 'Certificado ou chave TLS não encontrado.' }
    $arTls = @('--ssl-certfile', $CertFile, '--ssl-keyfile', $KeyFile)
    $env:COOKIE_SECURE = 'true'
}
& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn app:app --host $arBind --port 8080 --no-access-log --no-proxy-headers @arTls

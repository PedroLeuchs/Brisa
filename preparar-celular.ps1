param(
    [string]$Address,
    [string]$OutputDirectory = (Join-Path $PSScriptRoot 'data\mobile-tls'),
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

if (-not $Address) {
    $candidates = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
        Where-Object {
            $_.AddressState -eq 'Preferred' -and
            $_.IPAddress -notlike '127.*' -and
            $_.IPAddress -notlike '169.254.*'
        }
    if ($candidates.Count -ne 1) {
        throw 'Nao foi possivel escolher um unico IP local. Informe -Address, por exemplo: -Address 192.168.1.5'
    }
    $Address = $candidates[0].IPAddress
}

$arguments = @(
    (Join-Path $PSScriptRoot 'backend\tools\generate_mobile_certificate.py'),
    '--address', $Address,
    '--output', $OutputDirectory
)
if ($Force) { $arguments += '--force' }
& "$PSScriptRoot\.venv\Scripts\python.exe" @arguments
if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel gerar a preparacao HTTPS.' }

$keyPath = Join-Path $OutputDirectory 'brisa-server.key'
& icacls.exe $keyPath /inheritance:r /grant:r "$($env:USERNAME):(R,W)" 'SYSTEM:(F)' | Out-Null

Write-Host "Preparacao HTTPS criada para https://${Address}:8443"
Write-Host "Certificado publico para instalar no celular: $(Join-Path $OutputDirectory 'brisa-ca.crt')"
Write-Host 'Nenhuma porta foi aberta e o servidor atual nao foi reiniciado.'

$ErrorActionPreference = 'Stop'
$token = (Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'data\vercel-proxy.token')).Trim()
if ($token.Length -lt 32) { throw 'Execute instalar-inicio-brisa.ps1 primeiro.' }
Set-Clipboard -Value $token
$token = $null
Write-Host 'Token copiado. Cole diretamente em BRISA_PROXY_TOKEN no gerenciador de variaveis da Vercel; nao envie pelo chat. Depois limpe a area de transferencia.'

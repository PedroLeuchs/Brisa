$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& "$PSScriptRoot\.venv\Scripts\python.exe" "$PSScriptRoot\setup.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$arUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls.exe "$PSScriptRoot\.env" /inheritance:r /grant:r "${arUser}:(F)" 'SYSTEM:(F)' | Out-Null
Write-Host 'Arquivo .env restrito ao seu usuário e ao sistema.'

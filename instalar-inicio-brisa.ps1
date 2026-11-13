param([switch]$StartNow, [switch]$Remove)
$ErrorActionPreference = 'Stop'
$taskName = 'BrisaHome'
if ($Remove) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host 'Inicializacao automatica removida. O tunel e os dados nao foram apagados.'
    exit
}
if (-not (Test-Path "$PSScriptRoot\.venv\Scripts\python.exe")) { throw 'Prepare primeiro o ambiente Python do projeto existente.' }
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$others = Get-ScheduledTask | Where-Object {
    $_.TaskName -ne $taskName -and ($_.Actions | Where-Object { $_.Arguments -like "*$PSScriptRoot*" })
}
if ($others) { throw 'Ja existe outra tarefa para este projeto. Revise-a antes de instalar um segundo iniciador.' }
$dataPath = Join-Path $PSScriptRoot 'data'
New-Item -ItemType Directory -Path $dataPath -Force | Out-Null
$tokenPath = Join-Path $dataPath 'vercel-proxy.token'
if (-not (Test-Path -LiteralPath $tokenPath)) {
    $bytes = New-Object byte[] 32
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $random.GetBytes($bytes) } finally { $random.Dispose() }
    $token = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
    [IO.File]::WriteAllText($tokenPath, $token)
    $token = $null
}
& icacls.exe $tokenPath /inheritance:r /grant:r "${user}:(R,W)" '*S-1-5-18:(F)' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Falha ao proteger o token local. A tarefa nao foi instalada.' }
if ((Get-Content -Raw -LiteralPath $tokenPath).Trim().Length -lt 32) { throw 'Token local invalido. A tarefa nao foi instalada.' }
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$runner = Join-Path $PSScriptRoot 'iniciar-brisa-remoto.ps1'
$arguments = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`""
$action = New-ScheduledTaskAction -Execute $powershell -Argument $arguments -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Brisa local para acesso privado pela Vercel. Inicia ao entrar no Windows.' -Force | Out-Null
Write-Host 'Brisa configurado para iniciar em segundo plano ao entrar neste usuario do Windows.'
Write-Host 'Bloquear a tela nao encerra o Brisa. Sair da conta, suspender ou desligar interrompe o acesso.'
if ($StartNow) {
    if (Get-NetTCPConnection -State Listen -LocalPort 8080,8443 -ErrorAction SilentlyContinue) {
        Write-Host 'Existe um servidor em 8080/8443. Ele foi preservado; coordene a troca antes de iniciar a tarefa BrisaHome.'
    } else { Start-ScheduledTask -TaskName $taskName }
}

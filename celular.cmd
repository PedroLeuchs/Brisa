@echo off
cd /d "%~dp0"
echo O acesso pelo celular agora exige HTTPS e uma regra restrita do firewall.
echo Consulte a secao "Acesso pelo celular" no README antes de continuar.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar-celular.ps1"
pause

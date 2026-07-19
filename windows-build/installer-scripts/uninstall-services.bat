@echo off
REM ===================================================================
REM 卸载所有 Windows 服务（供 Inno Setup 卸载器调用）
REM ===================================================================

setlocal
set INSTALL_DIR=%~dp0..
set NSSM=%INSTALL_DIR%\nssm\nssm.exe

echo Stopping services...
net stop ProcessOptApi 2>nul
net stop ProcessOptConsumer 2>nul
net stop ProcessOptGateway 2>nul
net stop ProcessOptNats 2>nul
net stop ProcessOptPostgres 2>nul

echo Removing services...
"%NSSM%" remove ProcessOptApi confirm 2>nul
"%NSSM%" remove ProcessOptConsumer confirm 2>nul
"%NSSM%" remove ProcessOptGateway confirm 2>nul
"%NSSM%" remove ProcessOptNats confirm 2>nul
"%NSSM%" remove ProcessOptPostgres confirm 2>nul

echo Services removed.
exit /b 0

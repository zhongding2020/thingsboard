@echo off
setlocal

for %%I in ("%~dp0..") do set "INSTALL_DIR=%%~fI"
set "NSSM=%INSTALL_DIR%\nssm\nssm.exe"
set "LOGS=%INSTALL_DIR%\logs"

net session >nul 2>&1
if errorlevel 1 goto :not_admin
if not exist "%NSSM%" goto :missing_nssm
if not exist "%LOGS%" mkdir "%LOGS%"
if errorlevel 1 goto :error

echo Stopping existing services...
net stop ProcessOptApi >nul 2>&1
net stop ProcessOptConsumer >nul 2>&1
net stop ProcessOptGateway >nul 2>&1
net stop ProcessOptNats >nul 2>&1
net stop ProcessOptPostgres >nul 2>&1

echo Registering Windows services...

sc.exe query ProcessOptPostgres >nul 2>&1
if not errorlevel 1 goto :configure_postgres
"%NSSM%" install ProcessOptPostgres "%INSTALL_DIR%\postgresql\bin\postgres.exe" -D data
if errorlevel 1 goto :error
:configure_postgres
"%NSSM%" set ProcessOptPostgres DisplayName "ProcessOpt - PostgreSQL"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptPostgres Description "PostgreSQL 15 for ProcessOpt"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptPostgres AppDirectory "%INSTALL_DIR%\postgresql"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptPostgres AppParameters "-D data"
if errorlevel 1 goto :error
icacls "%INSTALL_DIR%\postgresql\data" /grant "*S-1-5-20:(OI)(CI)M" /T /C >nul
if errorlevel 1 goto :error
icacls "%LOGS%" /grant "*S-1-5-20:(OI)(CI)M" /T /C >nul
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptPostgres ObjectName "NT AUTHORITY\NetworkService"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptPostgres Start SERVICE_AUTO_START
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptPostgres AppStdout "%LOGS%\postgres.log"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptPostgres AppStderr "%LOGS%\postgres.log"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptPostgres AppRotateFiles 1
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptPostgres AppRotateBytes 10485760
if errorlevel 1 goto :error

sc.exe query ProcessOptNats >nul 2>&1
if not errorlevel 1 goto :configure_nats
"%NSSM%" install ProcessOptNats "%INSTALL_DIR%\nats\nats-server.exe" -js -sd data -p 4222
if errorlevel 1 goto :error
:configure_nats
"%NSSM%" set ProcessOptNats DisplayName "ProcessOpt - NATS"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptNats Description "NATS JetStream for ProcessOpt"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptNats AppDirectory "%INSTALL_DIR%\nats"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptNats AppParameters "-js -sd data -p 4222"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptNats Start SERVICE_AUTO_START
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptNats AppStdout "%LOGS%\nats.log"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptNats AppStderr "%LOGS%\nats.log"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptNats AppRotateFiles 1
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptNats AppRotateBytes 10485760
if errorlevel 1 goto :error

sc.exe query ProcessOptGateway >nul 2>&1
if not errorlevel 1 goto :configure_gateway
"%NSSM%" install ProcessOptGateway "%INSTALL_DIR%\app\python\python.exe" -m process_opt.gateway.main
if errorlevel 1 goto :error
:configure_gateway
"%NSSM%" set ProcessOptGateway DisplayName "ProcessOpt - Gateway"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptGateway Description "HTTP data ingestion gateway (port 8001)"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptGateway AppDirectory "%INSTALL_DIR%\app"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptGateway AppEnvironmentExtra "PYTHONPATH=%INSTALL_DIR%\app"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptGateway Start SERVICE_AUTO_START
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptGateway DependOnService ProcessOptNats
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptGateway AppStdout "%LOGS%\gateway.log"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptGateway AppStderr "%LOGS%\gateway.log"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptGateway AppRotateFiles 1
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptGateway AppRotateBytes 10485760
if errorlevel 1 goto :error

sc.exe query ProcessOptConsumer >nul 2>&1
if not errorlevel 1 goto :configure_consumer
"%NSSM%" install ProcessOptConsumer "%INSTALL_DIR%\app\python\python.exe" -m process_opt.consumer.main
if errorlevel 1 goto :error
:configure_consumer
"%NSSM%" set ProcessOptConsumer DisplayName "ProcessOpt - Consumer"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptConsumer Description "NATS-to-PostgreSQL consumer worker"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptConsumer AppDirectory "%INSTALL_DIR%\app"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptConsumer AppEnvironmentExtra "PYTHONPATH=%INSTALL_DIR%\app"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptConsumer Start SERVICE_AUTO_START
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptConsumer DependOnService ProcessOptPostgres ProcessOptNats
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptConsumer AppStdout "%LOGS%\consumer.log"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptConsumer AppStderr "%LOGS%\consumer.log"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptConsumer AppRotateFiles 1
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptConsumer AppRotateBytes 10485760
if errorlevel 1 goto :error

sc.exe query ProcessOptApi >nul 2>&1
if not errorlevel 1 goto :configure_api
"%NSSM%" install ProcessOptApi "%INSTALL_DIR%\app\python\python.exe" -m process_opt.api.main
if errorlevel 1 goto :error
:configure_api
"%NSSM%" set ProcessOptApi DisplayName "ProcessOpt - Web"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptApi Description "Backend API and frontend (port 8000)"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptApi AppDirectory "%INSTALL_DIR%\app"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptApi AppEnvironmentExtra "PYTHONPATH=%INSTALL_DIR%\app"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptApi Start SERVICE_AUTO_START
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptApi DependOnService ProcessOptPostgres
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptApi AppStdout "%LOGS%\api.log"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptApi AppStderr "%LOGS%\api.log"
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptApi AppRotateFiles 1
if errorlevel 1 goto :error
"%NSSM%" set ProcessOptApi AppRotateBytes 10485760
if errorlevel 1 goto :error

echo Services registered. Starting...
net start ProcessOptPostgres
if errorlevel 1 goto :error
net start ProcessOptNats
if errorlevel 1 goto :error
net start ProcessOptGateway
if errorlevel 1 goto :error
net start ProcessOptConsumer
if errorlevel 1 goto :error
net start ProcessOptApi
if errorlevel 1 goto :error

echo All services started.
exit /b 0

:not_admin
echo ERROR: Run this script as Administrator.
exit /b 1

:missing_nssm
echo ERROR: NSSM was not found at "%NSSM%".
exit /b 1

:error
echo ERROR: Service installation or startup failed.
exit /b 1

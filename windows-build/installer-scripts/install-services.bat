@echo off
REM ===================================================================
REM 注册 5 个 Windows 服务
REM ===================================================================

setlocal
set INSTALL_DIR=%~dp0..
set NSSM=%INSTALL_DIR%\nssm\nssm.exe
set LOGS=%INSTALL_DIR%\logs
if not exist "%LOGS%" mkdir "%LOGS%"

echo Registering Windows services...

REM ── 1. PostgreSQL ──
"%NSSM%" install ProcessOptPostgres "%INSTALL_DIR%\postgresql\bin\postgres.exe" ^
    -D "%INSTALL_DIR%\postgresql\data"
"%NSSM%" set ProcessOptPostgres DisplayName "工艺优化-数据库"
"%NSSM%" set ProcessOptPostgres Description "PostgreSQL 15 for ProcessOpt"
"%NSSM%" set ProcessOptPostgres Start SERVICE_AUTO_START
"%NSSM%" set ProcessOptPostgres AppStdout "%LOGS%\postgres.log"
"%NSSM%" set ProcessOptPostgres AppStderr "%LOGS%\postgres.log"
"%NSSM%" set ProcessOptPostgres AppRotateFiles 1
"%NSSM%" set ProcessOptPostgres AppRotateBytes 10485760

REM ── 2. NATS ──
"%NSSM%" install ProcessOptNats "%INSTALL_DIR%\nats\nats-server.exe" ^
    -js -sd "%INSTALL_DIR%\nats\data" -p 4222
"%NSSM%" set ProcessOptNats DisplayName "工艺优化-消息队列"
"%NSSM%" set ProcessOptNats Description "NATS JetStream for ProcessOpt"
"%NSSM%" set ProcessOptNats Start SERVICE_AUTO_START
"%NSSM%" set ProcessOptNats AppStdout "%LOGS%\nats.log"
"%NSSM%" set ProcessOptNats AppStderr "%LOGS%\nats.log"
"%NSSM%" set ProcessOptNats AppRotateFiles 1
"%NSSM%" set ProcessOptNats AppRotateBytes 10485760

REM ── 3. Gateway (HTTP 数据接入网关，端口 8001) ──
"%NSSM%" install ProcessOptGateway "%INSTALL_DIR%\app\python\python.exe" ^
    -m process_opt.gateway.main
"%NSSM%" set ProcessOptGateway DisplayName "工艺优化-数据网关"
"%NSSM%" set ProcessOptGateway Description "HTTP data ingestion gateway (port 8001)"
"%NSSM%" set ProcessOptGateway AppDirectory "%INSTALL_DIR%\app"
"%NSSM%" set ProcessOptGateway AppEnvironmentExtra PYTHONPATH="%INSTALL_DIR%\app"
"%NSSM%" set ProcessOptGateway Start SERVICE_AUTO_START
"%NSSM%" set ProcessOptGateway DependOnService ProcessOptNats
"%NSSM%" set ProcessOptGateway AppStdout "%LOGS%\gateway.log"
"%NSSM%" set ProcessOptGateway AppStderr "%LOGS%\gateway.log"
"%NSSM%" set ProcessOptGateway AppRotateFiles 1
"%NSSM%" set ProcessOptGateway AppRotateBytes 10485760

REM ── 4. Consumer (NATS → PostgreSQL) ──
"%NSSM%" install ProcessOptConsumer "%INSTALL_DIR%\app\python\python.exe" ^
    -m process_opt.consumer.main
"%NSSM%" set ProcessOptConsumer DisplayName "工艺优化-数据消费"
"%NSSM%" set ProcessOptConsumer Description "NATS-to-PostgreSQL consumer worker"
"%NSSM%" set ProcessOptConsumer AppDirectory "%INSTALL_DIR%\app"
"%NSSM%" set ProcessOptConsumer AppEnvironmentExtra PYTHONPATH="%INSTALL_DIR%\app"
"%NSSM%" set ProcessOptConsumer Start SERVICE_AUTO_START
"%NSSM%" set ProcessOptConsumer DependOnService ProcessOptPostgres ProcessOptNats
"%NSSM%" set ProcessOptConsumer AppStdout "%LOGS%\consumer.log"
"%NSSM%" set ProcessOptConsumer AppStderr "%LOGS%\consumer.log"
"%NSSM%" set ProcessOptConsumer AppRotateFiles 1
"%NSSM%" set ProcessOptConsumer AppRotateBytes 10485760

REM ── 5. Backend API + Frontend (端口 8000) ──
"%NSSM%" install ProcessOptApi "%INSTALL_DIR%\app\python\python.exe" ^
    -m process_opt.api.main
"%NSSM%" set ProcessOptApi DisplayName "工艺优化-Web服务"
"%NSSM%" set ProcessOptApi Description "Backend API + Frontend (port 8000)"
"%NSSM%" set ProcessOptApi AppDirectory "%INSTALL_DIR%\app"
"%NSSM%" set ProcessOptApi AppEnvironmentExtra PYTHONPATH="%INSTALL_DIR%\app"
"%NSSM%" set ProcessOptApi Start SERVICE_AUTO_START
"%NSSM%" set ProcessOptApi DependOnService ProcessOptPostgres
"%NSSM%" set ProcessOptApi AppStdout "%LOGS%\api.log"
"%NSSM%" set ProcessOptApi AppStderr "%LOGS%\api.log"
"%NSSM%" set ProcessOptApi AppRotateFiles 1
"%NSSM%" set ProcessOptApi AppRotateBytes 10485760

echo Services registered. Starting...
net start ProcessOptPostgres
net start ProcessOptNats
net start ProcessOptGateway
net start ProcessOptConsumer
net start ProcessOptApi

echo All services started.
exit /b 0

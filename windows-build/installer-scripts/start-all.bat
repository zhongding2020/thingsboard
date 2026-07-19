@echo off
REM 启动所有服务
net start ProcessOptPostgres
net start ProcessOptNats
net start ProcessOptGateway
net start ProcessOptConsumer
net start ProcessOptApi
echo All services started. Open http://localhost:8000
pause

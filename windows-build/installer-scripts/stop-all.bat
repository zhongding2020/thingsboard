@echo off
REM 停止所有服务（按依赖倒序）
net stop ProcessOptApi
net stop ProcessOptConsumer
net stop ProcessOptGateway
net stop ProcessOptNats
net stop ProcessOptPostgres
echo All services stopped.
pause

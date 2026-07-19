@echo off
REM ===================================================================
REM 首次初始化 PostgreSQL 数据库
REM 由安装器在安装完成后自动调用一次
REM ===================================================================

setlocal
set INSTALL_DIR=%~dp0..
set PG_DIR=%INSTALL_DIR%\postgresql
set PG_DATA=%PG_DIR%\data
set PG_LOG=%INSTALL_DIR%\logs\postgres-init.log

if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"

echo [%date% %time%] Initializing PostgreSQL... > "%PG_LOG%"

REM 已经初始化过，跳过
if exist "%PG_DATA%\PG_VERSION" (
    echo Database already initialized.
    echo [%date% %time%] Skipped: already initialized. >> "%PG_LOG%"
    goto :migrations
)

REM 1. initdb — UTF-8 编码，C locale（避免 Windows 中文 locale 引起的排序问题）
echo Creating PostgreSQL data directory...
"%PG_DIR%\bin\initdb.exe" ^
    -D "%PG_DATA%" ^
    -U postgres ^
    --pwfile="%~dp0pg-password.txt" ^
    --encoding=UTF8 ^
    --locale=C >> "%PG_LOG%" 2>&1

if errorlevel 1 (
    echo initdb failed. See %PG_LOG%
    exit /b 1
)

REM 2. 修改 postgresql.conf 端口为 5432 (默认)，只监听 localhost
echo listen_addresses = 'localhost' >> "%PG_DATA%\postgresql.conf"
echo port = 5432 >> "%PG_DATA%\postgresql.conf"

REM 3. 临时启动 postgres 以创建业务库
echo Starting PostgreSQL temporarily...
start /B "" "%PG_DIR%\bin\postgres.exe" -D "%PG_DATA%"

REM 等待 postgres 就绪
set /a WAIT_COUNT=0
:wait_pg
timeout /t 1 /nobreak > nul
"%PG_DIR%\bin\pg_isready.exe" -h localhost -p 5432 -U postgres > nul 2>&1
if not errorlevel 1 goto pg_ready
set /a WAIT_COUNT+=1
if %WAIT_COUNT% GEQ 30 (
    echo PostgreSQL failed to start in 30s.
    exit /b 1
)
goto wait_pg
:pg_ready
echo PostgreSQL ready.

REM 4. 创建业务数据库
echo Creating database process_opt...
"%PG_DIR%\bin\psql.exe" -h localhost -U postgres -c "CREATE DATABASE process_opt;" >> "%PG_LOG%" 2>&1

:migrations
echo Applying migrations...
for %%f in ("%INSTALL_DIR%\app\db\migrations\*.sql") do (
    echo   %%~nxf
    "%PG_DIR%\bin\psql.exe" -h localhost -U postgres -d process_opt -f "%%f" >> "%PG_LOG%" 2>&1
)

REM 5. 停止临时 postgres — 后续由服务接管
"%PG_DIR%\bin\pg_ctl.exe" -D "%PG_DATA%" stop -m fast >> "%PG_LOG%" 2>&1

echo Initialization complete.
echo [%date% %time%] Done. >> "%PG_LOG%"
exit /b 0

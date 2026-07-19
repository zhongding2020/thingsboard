@echo off
setlocal

for %%I in ("%~dp0..") do set "INSTALL_DIR=%%~fI"
set "PG_DIR=%INSTALL_DIR%\postgresql"
set "PG_DATA=%PG_DIR%\data"
set "PG_LOG=%INSTALL_DIR%\logs\postgres-init.log"
set "PG_PASSWORD_FILE=%TEMP%\process-opt-pg-password-%RANDOM%.txt"
set "PGPASSWORD=postgres"
set "PG_STARTED=0"

if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"
if errorlevel 1 goto :error

echo [%date% %time%] Initializing PostgreSQL... > "%PG_LOG%"

if exist "%PG_DATA%\PG_VERSION" goto :start_postgres

echo Creating PostgreSQL data directory...
> "%PG_PASSWORD_FILE%" echo postgres
"%PG_DIR%\bin\initdb.exe" -D "%PG_DATA%" -U postgres --pwfile="%PG_PASSWORD_FILE%" --encoding=UTF8 --locale=C >> "%PG_LOG%" 2>&1
set "INITDB_EXIT=%errorlevel%"
del /q "%PG_PASSWORD_FILE%" >nul 2>&1
if not "%INITDB_EXIT%"=="0" goto :error

echo listen_addresses = 'localhost' >> "%PG_DATA%\postgresql.conf"
echo port = 5432 >> "%PG_DATA%\postgresql.conf"

:start_postgres
"%PG_DIR%\bin\pg_isready.exe" -h localhost -p 5432 -U postgres >nul 2>&1
if not errorlevel 1 goto :postgres_ready

echo Starting PostgreSQL temporarily...
"%PG_DIR%\bin\pg_ctl.exe" -D "%PG_DATA%" -l "%INSTALL_DIR%\logs\postgres-init-server.log" start >nul 2>&1
if errorlevel 1 goto :error
set "PG_STARTED=1"

set /a WAIT_COUNT=0
:wait_postgres
"%PG_DIR%\bin\pg_isready.exe" -h localhost -p 5432 -U postgres >nul 2>&1
if not errorlevel 1 goto :postgres_ready
set /a WAIT_COUNT+=1
if %WAIT_COUNT% GEQ 30 goto :timeout
timeout /t 1 /nobreak >nul
goto :wait_postgres

:postgres_ready
echo PostgreSQL ready.
"%PG_DIR%\bin\psql.exe" -h localhost -U postgres -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='process_opt'" | findstr /x "1" >nul
if not errorlevel 1 goto :migrations

echo Creating database process_opt...
"%PG_DIR%\bin\createdb.exe" -h localhost -U postgres process_opt >> "%PG_LOG%" 2>&1
if errorlevel 1 goto :error

:migrations
echo Applying migrations...
for %%F in ("%INSTALL_DIR%\app\db\migrations\*.sql") do call :apply_migration "%%~fF" || goto :error

if "%PG_STARTED%"=="1" "%PG_DIR%\bin\pg_ctl.exe" -D "%PG_DATA%" stop -m fast >> "%PG_LOG%" 2>&1
if errorlevel 1 goto :error

echo Initialization complete.
echo [%date% %time%] Done. >> "%PG_LOG%"
exit /b 0

:apply_migration
echo   %~nx1
"%PG_DIR%\bin\psql.exe" -v ON_ERROR_STOP=1 -h localhost -U postgres -d process_opt -f "%~1" >> "%PG_LOG%" 2>&1
exit /b %errorlevel%

:timeout
echo ERROR: PostgreSQL failed to start in 30 seconds.
goto :error

:error
del /q "%PG_PASSWORD_FILE%" >nul 2>&1
if "%PG_STARTED%"=="1" "%PG_DIR%\bin\pg_ctl.exe" -D "%PG_DATA%" stop -m fast >> "%PG_LOG%" 2>&1
echo ERROR: Database initialization failed. See "%PG_LOG%".
exit /b 1

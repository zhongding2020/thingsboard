@echo off
REM 导入 Mock 测试数据（5000 条记录）
setlocal
set INSTALL_DIR=%~dp0..

echo Importing mock data (5000 records)...
"%INSTALL_DIR%\app\python\python.exe" -m process_opt.mock.cli seed-db ^
    --dsn "postgresql://postgres:postgres@localhost:5432/process_opt" ^
    --records 5000

if errorlevel 1 (
    echo Import failed. Check that PostgreSQL service is running.
    pause
    exit /b 1
)

echo Mock data imported successfully.
pause

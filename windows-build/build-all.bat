@echo off
REM ==================================================================
REM 一键构建 Windows 安装包
REM 需要：Python 3.11+ x64, Node.js, Inno Setup 6.x
REM ==================================================================

setlocal
cd /d %~dp0

echo === Step 1: Building frontend ===
cd ..\web
call npm install
if errorlevel 1 (
    echo Frontend npm install failed.
    exit /b 1
)
call npm run build
if errorlevel 1 (
    echo Frontend build failed.
    exit /b 1
)

echo === Step 2: Packaging application ===
cd ..\windows-build\build-scripts
python build-package.py
if errorlevel 1 (
    echo Packaging failed.
    exit /b 1
)

echo === Step 3: Building installer ===
cd ..\installer-scripts
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    echo Inno Setup 6 not found. Install from https://jrsoftware.org/isdl.php
    exit /b 1
)
%ISCC% installer.iss
if errorlevel 1 (
    echo Installer build failed.
    exit /b 1
)

echo.
echo === Build complete ===
dir /b ..\build\output\*.exe
echo Output: %CD%\..\build\output\
pause

@echo off
setlocal

set "WINDOWS_BUILD=%~dp0"
for %%I in ("%WINDOWS_BUILD%..") do set "PROJECT_ROOT=%%~fI"
set "NPM_EXE="
set "PYTHON_EXE="
set "PYTHON_ARGS="
set "ISCC_EXE="

if not "%PROCESS_OPT_NPM%"=="" set "NPM_EXE=%PROCESS_OPT_NPM%"
if defined NPM_EXE goto npm_found
for /f "delims=" %%I in ('where npm.cmd 2^>nul') do if not defined NPM_EXE set "NPM_EXE=%%I"
if defined NPM_EXE goto npm_found
if exist "D:\Program Files\nodejs\npm.cmd" set "NPM_EXE=D:\Program Files\nodejs\npm.cmd"
if not defined NPM_EXE goto npm_missing
:npm_found

if not "%PROCESS_OPT_PYTHON%"=="" set "PYTHON_EXE=%PROCESS_OPT_PYTHON%"
if defined PYTHON_EXE goto python_found
if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if defined PYTHON_EXE goto python_found
py -3.11 --version >nul 2>&1
if not errorlevel 1 set "PYTHON_EXE=py"
if defined PYTHON_EXE set "PYTHON_ARGS=-3.11"
if defined PYTHON_EXE goto python_found
python --version >nul 2>&1
if not errorlevel 1 set "PYTHON_EXE=python"
if not defined PYTHON_EXE goto python_missing
:python_found

if not "%PROCESS_OPT_ISCC%"=="" set "ISCC_EXE=%PROCESS_OPT_ISCC%"
if defined ISCC_EXE goto iscc_found
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_EXE=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if defined ISCC_EXE goto iscc_found
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC_EXE=C:\Program Files\Inno Setup 6\ISCC.exe"
if defined ISCC_EXE goto iscc_found
for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do if not defined ISCC_EXE set "ISCC_EXE=%%I"
if not defined ISCC_EXE goto iscc_missing
:iscc_found

echo [1/3] Installing frontend dependencies...
pushd "%PROJECT_ROOT%\web"
call "%NPM_EXE%" install
if errorlevel 1 goto frontend_install_failed

echo [1/3] Building frontend...
call "%NPM_EXE%" run build
if errorlevel 1 goto frontend_build_failed
popd

echo [2/3] Packaging application...
pushd "%WINDOWS_BUILD%build-scripts"
"%PYTHON_EXE%" %PYTHON_ARGS% build-package.py
if errorlevel 1 goto package_failed
popd

echo [3/3] Building installer...
pushd "%WINDOWS_BUILD%installer-scripts"
"%ISCC_EXE%" installer.iss
if errorlevel 1 goto installer_failed
popd

echo.
echo Build completed successfully:
for %%I in ("%WINDOWS_BUILD%build\output\*.exe") do echo %%~fI
exit /b 0

:npm_missing
echo ERROR: Node.js npm.cmd was not found.
goto failed

:python_missing
echo ERROR: Python was not found. Python 3.11 x64 is required.
goto failed

:iscc_missing
echo ERROR: Inno Setup 6 ISCC.exe was not found.
goto failed

:frontend_install_failed
echo ERROR: Frontend dependency installation failed.
goto failed

:frontend_build_failed
echo ERROR: Frontend build failed.
goto failed

:package_failed
echo ERROR: Application packaging failed.
goto failed

:installer_failed
echo ERROR: Installer build failed.
goto failed

:failed
popd 2>nul
exit /b 1

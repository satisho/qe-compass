@echo off
setlocal
title QE Compass
cd /d "%~dp0"

rem ---- find Python 3.10+ ------------------------------------------------
set "PY="
where py >nul 2>nul && (py -3 -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set "PY=py -3")
if not defined PY (
  where python >nul 2>nul && (python -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set "PY=python")
)
if not defined PY (
  echo.
  echo  QE Compass needs Python 3.10 or newer.
  echo  Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^),
  echo  or from the Microsoft Store, then run start.bat again.
  echo.
  pause
  exit /b 1
)

rem ---- create the private environment on first run ---------------------
if not exist ".venv\Scripts\python.exe" (
  echo Setting up QE Compass for first use. This takes a minute...
  %PY% -m venv .venv || goto :fail
)

rem ---- install or update dependencies when requirements change ---------
fc /b "backend\requirements.txt" ".venv\installed-requirements.txt" >nul 2>nul
if errorlevel 1 (
  echo Installing components...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r backend\requirements.txt || goto :fail
  copy /y "backend\requirements.txt" ".venv\installed-requirements.txt" >nul
)

rem ---- run --------------------------------------------------------------
cd backend
"..\.venv\Scripts\python.exe" -m app --open %*
goto :eof

:fail
echo.
echo  Setup failed. If you are on a corporate network, pip may need your proxy:
echo    set HTTPS_PROXY=http://your-proxy:port   then run start.bat again.
echo  See README.md, "Troubleshooting".
pause
exit /b 1

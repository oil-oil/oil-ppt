@echo off
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0oil_ppt.py" %*
  exit /b %errorlevel%
)
where python >nul 2>nul
if %errorlevel%==0 (
  python "%~dp0oil_ppt.py" %*
  exit /b %errorlevel%
)
echo oil-ppt requires Python 3.10 or newer. 1>&2
exit /b 1

@echo off
setlocal
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"
pushd "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
  py -3.12 -B tools\windows_checker.py run %*
) else (
  python -B tools\windows_checker.py run %*
)
set "checker_rc=%errorlevel%"
popd
if not "%checker_rc%"=="0" echo Checker stopped safely. Review the error above; Cementing App was not changed.
pause
exit /b %checker_rc%

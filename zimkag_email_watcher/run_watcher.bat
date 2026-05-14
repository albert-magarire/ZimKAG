@echo off
setlocal

REM ───────────────────────────────────────────────────────────────────────
REM ZimKAG Email Watcher — Windows launcher
REM Creates .venv on first run, installs deps, then starts the watcher.
REM ───────────────────────────────────────────────────────────────────────

cd /d "%~dp0"

if not exist .env (
  if exist .env.example (
    copy .env.example .env >nul
    echo [setup] Created .env from .env.example — review settings before continuing.
  )
)

if not exist credentials\client_secret.json (
  echo.
  echo [error] Missing credentials\client_secret.json
  echo.
  echo Follow the 5-minute setup in credentials\README.md to create one.
  echo Without it the watcher cannot authenticate with Gmail.
  echo.
  pause
  exit /b 1
)

if not exist .venv (
  echo [setup] Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo [error] Failed to create venv. Is Python 3.10+ on PATH?
    exit /b 1
  )
  call .venv\Scripts\activate.bat
  echo [setup] Installing dependencies...
  python -m pip install --upgrade pip
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)

echo.
echo ──────────────────────────────────────────────────────
echo  ZimKAG Email Watcher starting...
echo  First run will open your browser to grant Gmail access.
echo  Press Ctrl+C to stop.
echo ──────────────────────────────────────────────────────
echo.

python -m zimkag_email_watcher.watcher

endlocal

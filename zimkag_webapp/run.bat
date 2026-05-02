@echo off
setlocal

REM ───────────────────────────────────────────────────────────────────────
REM ZimKAG launcher — Windows
REM Creates .venv on first run, installs deps, then starts the FastAPI app.
REM ───────────────────────────────────────────────────────────────────────

cd /d "%~dp0"

if not exist .env (
  if exist .env.example (
    copy .env.example .env >nul
    echo [setup] Created .env from .env.example — add your GROQ_API_KEY before re-running.
  )
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
echo  ZimKAG starting at http://127.0.0.1:8000
echo  Press Ctrl+C to stop.
echo ──────────────────────────────────────────────────────
echo.

python -m backend.app

endlocal

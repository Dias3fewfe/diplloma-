@echo off
SET NODE_PATH=C:\tools\node-v20.18.0-win-x64
SET PATH=%NODE_PATH%;%PATH%
SET PROJECT_DIR=%~dp0

echo Starting Backend (FastAPI)...
start "Backend" cmd /k "cd /d %PROJECT_DIR% && uvicorn backend.main:app --reload --port 8000"

echo Starting Frontend (React)...
start "Frontend" cmd /k "SET PATH=%NODE_PATH%;%PATH% && cd /d %PROJECT_DIR%frontend && npm run dev"

echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo API Docs: http://localhost:8000/docs
echo.
echo Both servers are starting in separate windows.
pause

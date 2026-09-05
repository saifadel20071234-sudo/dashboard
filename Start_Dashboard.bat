@echo off
title PowerStep Grid System
echo ===================================================
echo Starting PowerStep Grid System (Backend + Frontend)
echo ===================================================

echo [1] Installing Backend Dependencies (if missing)...
cd backend
python -m pip install -r requirements.txt

echo [2] Starting FastAPI Backend (Port 8000)...
start "PowerStep Backend" cmd /c "python -m uvicorn server:app --host 0.0.0.0 --port 8000"
cd ..

echo [3] Starting Frontend UI Server (Port 5500)...
start "PowerStep Frontend" cmd /c "python -m http.server 5500"

echo Waiting for servers to initialize...
timeout /t 3 >nul

echo [4] Opening Dashboard...
start http://localhost:5500/

echo Done! System is running.
exit

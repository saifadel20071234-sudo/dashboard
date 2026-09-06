@echo off
title PowerStep System
echo ===================================================
echo Starting PowerStep System (Team Backend + Frontend)
echo ===================================================

echo [1] Installing Backend Dependencies (if missing)...
cd backend
python -m pip install -r requirements.txt

echo [2] Starting Team Backend main_system.py (Port 8000)...
start "PowerStep Backend" cmd /c "python main_system.py"
cd ..

echo [3] Starting Frontend UI Server (Port 5500)...
start "PowerStep Frontend" cmd /c "python -m http.server 5500"

echo Waiting for servers to initialize...
timeout /t 3 >nul

echo [4] Opening Dashboard...
start http://localhost:5500/

echo Done! Backend is on :8000, Dashboard is on :5500
exit
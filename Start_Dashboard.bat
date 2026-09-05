@echo off
title PowerStep Dashboard Server
echo ===================================================
echo Starting PowerStep Grid Dashboard Local Server...
echo ===================================================

:: تشغيل سيرفر بايثون في نافذة منفصلة
start "PowerStep Server" cmd /c "python -m http.server 5500"

:: الانتظار ثانيتين عشان السيرفر يلحق يشتغل
timeout /t 2 >nul

:: فتح صفحة لوحة التحكم الرئيسية فقط
start http://localhost:5500/

echo Done! Dashboard is open at http://localhost:5500/
exit

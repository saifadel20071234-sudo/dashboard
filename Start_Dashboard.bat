@echo off
title PowerStep Dashboard Server
echo ===================================================
echo Starting PowerStep Grid Dashboard Local Server...
echo ===================================================

:: تشغيل سيرفر بايثون في نافذة تانية مخفية أو منفصلة
start "PowerStep Server" cmd /c "python -m http.server 5500"

:: الانتظار ثانيتين عشان السيرفر يلحق يشتغل
timeout /t 2 >nul

:: فتح صفحة لوحة التحكم
start http://localhost:5500/

:: فتح صفحة التحليلات في تاب جديد
start http://localhost:5500/analytics.html

echo Done! The dashboard pages have been opened in your browser.
exit

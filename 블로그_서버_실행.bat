@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 경제 냠냠 블로그 서버 (Claude 칩섭 프록시)
echo ========================================
echo   경제 냠냠 블로그 스튜디오 서버
echo   Claude(칩섭) 프록시 포함
echo ========================================
echo.
echo  이 창을 닫으면 Claude 연결이 끊깁니다.
echo  주소: http://localhost:8000
echo.
where python >nul 2>&1
if errorlevel 1 (
  echo [오류] python 을 찾을 수 없습니다. Python 설치 후 다시 실행하세요.
  pause
  exit /b 1
)
python server.py
echo.
echo 서버가 종료되었습니다.
pause

@echo off
REM 종가 매매 스크리너 - 매일 자동 실행용
REM Windows 작업 스케줄러가 이 파일을 평일 15:05에 실행하도록 등록하세요.
cd /d "%~dp0"
python screen.py --open

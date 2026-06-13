@echo off
REM 종가 매매 - 매일 자동 실행용 (계산 후 GitHub에 올림 -> 클라우드 앱 갱신)
REM 작업 스케줄러에 평일 15:05로 등록하세요.
cd /d "%~dp0"
python publish.py

@echo off
rem M24GA CLI (터미널에서 쓰기). GUI 없이 모든 기능을 명령줄로 제어한다.
rem 사용: m24cli <명령> [옵션]          도움말: m24cli --help
cd /d "%~dp0"
python -X utf8 loader\cli.py %*

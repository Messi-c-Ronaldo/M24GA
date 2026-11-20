@echo off
rem M24GA 로더 앱 (더블클릭). 창을 닫으면 모드도 멈춘다.
rem frida, pywebview 등은 vendor\ 에 둔다:  pip install --target vendor frida pywebview
cd /d "%~dp0"
start "" pythonw -X utf8 loader\app.py

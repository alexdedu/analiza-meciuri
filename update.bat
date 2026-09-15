@echo off
REM Reimprospateaza predictiile: descarca rezultatele noi si regenereaza JSON-ul.
cd /d "%~dp0research"
.venv\Scripts\python.exe predict.py
echo.
echo Gata. Reconstruieste aplicatia cu:  cd app ^&^& flutter build apk --release --split-per-abi
pause

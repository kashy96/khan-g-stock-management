@echo off
rem Rebuilds KHAN_G_Stock.exe after you (or Claude) change main.py / db.py.
rem Result: dist\KHAN_G_Stock.exe  (a single file, no Python needed to run it)
cd /d "%~dp0"
python -m PyInstaller --onefile --windowed --name "KHAN_G_Stock" main.py
echo.
echo Done. The program is at: dist\KHAN_G_Stock.exe
pause

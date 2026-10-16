@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto try_python
py -3 -c "import sys, tkinter; assert sys.version_info >= (3, 10)" >nul 2>nul
if errorlevel 1 goto try_python
py -3 main.py
if errorlevel 1 pause
exit /b
:try_python
where python >nul 2>nul
if errorlevel 1 goto missing
python -c "import sys, tkinter; assert sys.version_info >= (3, 10)" >nul 2>nul
if errorlevel 1 goto missing
python main.py
if errorlevel 1 pause
exit /b
:missing
echo Python 3.10 veya ustu ve Tcl/Tk gerekiyor.
echo https://www.python.org/downloads/windows/ adresinden Python kur.
echo Kurulumda Tcl/Tk ve Python launcher seceneklerini etkin birak.
pause
exit /b 1

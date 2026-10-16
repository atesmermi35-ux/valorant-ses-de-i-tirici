@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "VB_LOG=%TEMP%\VoiceBridge-startup.log"
if not exist "main.py" goto incomplete
if not exist "voicebridge\gui.py" goto incomplete
where py >nul 2>nul
if errorlevel 1 goto try_python
py -3 -c "import sys, tkinter; assert sys.version_info >= (3, 10)" >nul 2>nul
if errorlevel 1 goto try_python
py -3 main.py 2>"%VB_LOG%"
if errorlevel 1 goto failed
exit /b
:try_python
where python >nul 2>nul
if errorlevel 1 goto missing
python -c "import sys, tkinter; assert sys.version_info >= (3, 10)" >nul 2>nul
if errorlevel 1 goto missing
python main.py 2>"%VB_LOG%"
if errorlevel 1 goto failed
exit /b
:missing
echo Python 3.10 veya ustu ve Tcl/Tk gerekiyor.
echo https://www.python.org/downloads/windows/ adresinden Python kur.
echo Kurulumda Tcl/Tk ve Python launcher seceneklerini etkin birak.
pause
exit /b 1
:incomplete
echo ZIP'in icinden calistiriyorsun veya uygulama dosyalari eksik.
echo ZIP dosyasina sag tikla, TUMUNU AYIKLA secenegine bas.
echo Sonra cikarilan klasordeki BASLAT.cmd dosyasini ac.
echo main.py ve voicebridge klasoru da yaninda olmali.
pause
exit /b 1
:failed
type "%VB_LOG%"
echo.
echo Hata raporu: "%VB_LOG%"
echo Rapor Not Defteri'nde acilacak. Hata metnini paylasabilirsin.
start "" notepad.exe "%VB_LOG%"
pause
exit /b 1

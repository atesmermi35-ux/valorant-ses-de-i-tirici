@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "PYTHONUTF8=1"
if not exist "voicebridge\natural.py" goto incomplete
if not exist "assets\voices\LJ001-0001.wav" goto incomplete
echo Dogal kadin sesi - kayit donusumu denemesi
echo Sonraki pencerede kendi ses kaydini ve sonuc dosyasinin yerini sec.
echo Ilk kurulum birkac GB indirir. Bu deneme canli oyun mikrofonu baglamaz.
py -3.12 -m voicebridge.natural local
set "VB_NATURAL_EXIT=%ERRORLEVEL%"
if not "%VB_NATURAL_EXIT%"=="0" echo Yukaridaki hata metnini paylasabilirsin.
pause
exit /b %VB_NATURAL_EXIT%
:incomplete
echo ZIP'e sag tiklayip TUMUNU AYIKLA sec ve cikarilan klasorden calistir.
pause
exit /b 1

@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "PYTHONUTF8=1"
if not exist "voicebridge\training.py" goto incomplete
echo Seed-VC kalite oncelikli egitim kurulumu.
echo Sonraki pencerede temiz tek konusmacili ses kayitlarinin klasorunu sec.
echo Kurulum birkac GB indirir. RTX 3050'de bellek kullanimi veriye baglidir.
py -3.12 -m voicebridge.training local
set "VB_MODEL_EXIT=%ERRORLEVEL%"
if not "%VB_MODEL_EXIT%"=="0" echo Islem tamamlanamadi. Yukaridaki hata metnini paylas.
pause
exit /b %VB_MODEL_EXIT%
:incomplete
echo ZIP'e sag tiklayip TUMUNU AYIKLA sec. Sonra bu dosyayi cikarilan klasorden ac.
pause
exit /b 1

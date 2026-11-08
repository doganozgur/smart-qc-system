@echo off
title SmartVisionQC Windows EXE Builder
echo ====================================================
echo   SmartVisionQC .EXE Dosyasina Donusturme Araci
echo ====================================================

REM Python kontrolu
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Python bulunamadi! Lutfen Python 3.10+ yukleyin ve PATH'e ekleyin.
    pause
    exit /b 1
)

echo [1/3] Gereksinimler kontrol ediliyor...
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo [2/3] .EXE Paketi olusturuluyor...
python build_windows_exe.py

echo.
echo [3/3] Tamamlandi! 'dist\SmartVisionQC' klasorundeki SmartVisionQC.exe dosyasini calistirabilirsiniz.
echo.
pause

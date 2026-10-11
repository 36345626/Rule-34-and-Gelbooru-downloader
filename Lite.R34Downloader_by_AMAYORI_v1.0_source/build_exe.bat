@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set "PY=py") || (set "PY=python")
echo Устанавливаю нужные библиотеки...
%PY% -m pip install --upgrade pip
%PY% -m pip install PySide6-Essentials requests PySocks websocket-client pyinstaller
if errorlevel 1 goto error
echo Собираю R34Downloader_by_AMAYORI.exe...
%PY% "R34Downloader_by_AMAYORI.py" --build %*
if errorlevel 1 goto error
echo.
if /i "%~1"=="--folder" (echo Готово: папка R34Downloader_by_AMAYORI\ рядом с этим файлом.) else (echo Готово: R34Downloader_by_AMAYORI.exe рядом с этим файлом.)
pause
exit /b 0
:error
echo.
echo Сборка не удалась — смотрите сообщения выше.
pause
exit /b 1

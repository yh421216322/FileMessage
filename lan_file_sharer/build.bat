@echo off
echo Building LANFileSharer executable...

REM Navigate to the script's directory (project root)
cd /D "%~dp0"

REM Activate virtual environment if it exists and is used (optional, depends on worker setup)
REM Example:
REM IF EXIST ".venv\Scripts\activate.bat" (
REM     echo Activating virtual environment...
REM     CALL .venv\Scripts\activate.bat
REM )

REM Ensure requirements are installed (optional, good practice for build scripts)
echo Installing/updating requirements...
pip install -r requirements.txt

echo Running PyInstaller...
pyinstaller --onefile --windowed --name LANFileSharer --distpath ./dist --workpath ./build src/main.py

IF %ERRORLEVEL% EQU 0 (
    echo.
    echo LANFileSharer.exe successfully built in the 'dist' directory.
    echo You can find it at: %~dp0dist\LANFileSharer.exe
) ELSE (
    echo.
    echo PyInstaller failed with error code %ERRORLEVEL%.
    echo Please check the output above for details.
)

REM Deactivate virtual environment if applicable
REM IF DEFINED VIRTUAL_ENV (
REM     echo Deactivating virtual environment...
REM     CALL deactivate
REM )

echo.
echo Build script finished.

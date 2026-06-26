@echo off
cd /d "%~dp0"
echo Starting preview server...

python --version >nul 2>&1
if %errorlevel%==0 (
    echo Using Python...
    start "" "http://localhost:8080"
    python -m http.server 8080
    goto end
)

py --version >nul 2>&1
if %errorlevel%==0 (
    echo Using py launcher...
    start "" "http://localhost:8080"
    py -m http.server 8080
    goto end
)

python3 --version >nul 2>&1
if %errorlevel%==0 (
    echo Using python3...
    start "" "http://localhost:8080"
    python3 -m http.server 8080
    goto end
)

npx --version >nul 2>&1
if %errorlevel%==0 (
    echo Using npx serve...
    start "" "http://localhost:3000"
    npx serve .
    goto end
)

echo.
echo ERROR: Could not find Python or Node.js.
echo Please install Python from https://python.org or Node.js from https://nodejs.org
echo Then re-run this file.
pause

:end

@echo off
echo Locating app on device...
set ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe
"%ADB%" devices
for /f "tokens=*" %%i in ('"%ADB%" shell pm path com.maverickinvestor.app') do set APK_PATH=%%i
set APK_PATH=%APK_PATH:package:=%
echo Found APK at: %APK_PATH%
echo Pulling APK...
"%ADB%" pull "%APK_PATH%" "%~dp0MaverickInvestor.apk"
echo.
echo Done! MaverickInvestor.apk saved to this folder.
pause

@echo off
setlocal enabledelayedexpansion

:: Auto-request admin privileges
if not "%1"=="admin" (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process -FilePath '%0' -ArgumentList 'admin' -Verb RunAs"
    exit /b
)

echo ===============================
echo Chrome Browser Installer
echo ===============================
echo.
echo Contact: WeChat wangdefa4567
echo.

echo Checking if Chrome is already installed...

:: Define all possible Chrome installation paths
set CHROME_PATHS="%ProgramFiles%\Google\Chrome\Application\chrome.exe"^
 "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"^
 "%LocalAppData%\Google\Chrome\Application\chrome.exe"^
 "C:\Program Files\Google\Chrome\Application\chrome.exe"^
 "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

set CHROME_FOUND=0

:: Check common Chrome installation paths
for %%i in (%CHROME_PATHS%) do (
    if exist %%i (
        echo Chrome is already installed at: %%i
        set CHROME_FOUND=1
    )
)

:: Try to find Chrome in registry
for /f "tokens=*" %%a in ('reg query "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" /ve 2^>nul ^| find "REG_SZ"') do (
    set CHROME_REG_PATH=%%a
    set CHROME_REG_PATH=!CHROME_REG_PATH:*REG_SZ    =!
    if exist "!CHROME_REG_PATH!" (
        echo Found Chrome in registry: !CHROME_REG_PATH!
        set CHROME_FOUND=1
    )
)

:: Ask user what to do if Chrome is found
if %CHROME_FOUND% equ 1 (
    echo.
    set /p REINSTALL="Chrome is already installed. Do you want to reinstall it anyway? (y/n): "
    if /i "!REINSTALL!"=="y" (
        goto :download_chrome
    ) else (
        echo Chrome installation skipped.
        goto :end
    )
)

:download_chrome
echo Chrome not found or reinstall requested.
echo.
echo Downloading Chrome installer...

:: Set temporary directory for the installer
set TEMP_DIR=%TEMP%\ChromeInstall
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"

:: Download Chrome installer with progress indicator
echo Downloading... This may take a few minutes depending on your internet speed.
powershell -Command "$ProgressPreference = 'SilentlyContinue'; (New-Object System.Net.WebClient).DownloadFile('https://dl.google.com/chrome/install/latest/chrome_installer.exe', '%TEMP_DIR%\chrome_installer.exe')"

if %errorlevel% neq 0 (
    echo Failed to download Chrome installer.
    echo Please check your internet connection and try again.
    goto :cleanup
)

echo Download completed.
echo.
echo Installing Chrome (this might take a few minutes)...

:: Install Chrome silently
start /wait "" "%TEMP_DIR%\chrome_installer.exe" /silent /install

echo.
echo Verifying installation...

:: Check if Chrome was installed successfully
timeout /t 5 /nobreak > nul

set CHROME_INSTALLED=0
for %%i in (%CHROME_PATHS%) do (
    if exist %%i (
        echo Chrome has been successfully installed at: %%i
        set CHROME_INSTALLED=1
        goto :installation_complete
    )
)

:: Try to find Chrome in registry again
for /f "tokens=*" %%a in ('reg query "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" /ve 2^>nul ^| find "REG_SZ"') do (
    set CHROME_REG_PATH=%%a
    set CHROME_REG_PATH=!CHROME_REG_PATH:*REG_SZ    =!
    if exist "!CHROME_REG_PATH!" (
        echo Chrome has been successfully installed at: !CHROME_REG_PATH!
        set CHROME_INSTALLED=1
        goto :installation_complete
    )
)

:installation_complete
if %CHROME_INSTALLED% equ 0 (
    echo.
    echo Chrome installation may have failed. Please try one of the following:
    echo 1. Run this script again
    echo 2. Install Chrome manually: https://www.google.com/chrome/
    echo 3. Contact support for assistance
)

:cleanup
echo.
echo Cleaning up temporary files...
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"

:end
echo.
echo Contact information:
echo WeChat: wangdefa4567
echo.
echo Press any key to exit...
pause > nul 
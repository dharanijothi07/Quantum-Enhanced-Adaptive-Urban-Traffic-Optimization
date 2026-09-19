@echo off
echo ========================================================
echo Starting QuantumFlow Vite + React Dashboard (Port 5173)
echo ========================================================
cd /d "%~dp0\..\frontend"
if exist "C:\Users\dhara\AppData\Local\node-v20.11.1-win-x64\node.exe" (
    set "PATH=C:\Users\dhara\AppData\Local\node-v20.11.1-win-x64;%PATH%"
)
npm run dev
pause

@echo off
setlocal
cd /d "%~dp0"
title EnterpriseAI temporary public preview

where docker >nul 2>&1
if errorlevel 1 (
  echo Docker CLI was not found. Open Docker Desktop and start the local application first.
  goto done
)
docker compose ps --status running web | findstr /I "web" >nul
if errorlevel 1 (
  echo Start the local application with Start-EnterpriseAI.cmd before opening a public preview.
  goto done
)

echo Starting a temporary Cloudflare Quick Tunnel.
echo Keep this window and your PC running while someone uses the link.
echo The generated URL is temporary; closing this window stops the public link.
docker compose --profile public-preview up -d cloudflared
if errorlevel 1 goto done
echo.
echo Find the https://...trycloudflare.com URL below and share it only with the intended viewer.
docker compose --profile public-preview logs --follow cloudflared

:done
echo.
pause
endlocal


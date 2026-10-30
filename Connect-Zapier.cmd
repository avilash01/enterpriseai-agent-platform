@echo off
setlocal
cd /d "%~dp0"
title EnterpriseAI Zapier connection

if not exist .env (
  echo ERROR: .env is missing. Start EnterpriseAI first, then retry.
  goto done
)

echo.
echo  Connect EnterpriseAI to your Zapier Catch Hook
echo  ===============================================
echo In Zapier, create or regenerate a Webhooks by Zapier Catch Hook URL.
echo Keep that URL private. It authorizes anyone holding it to send events to your Zap.
echo.
echo Notepad will open this project's private .env file. Set ZAPIER_WEBHOOK_URL to the new URL,
echo save the file, and close Notepad. Do not paste the URL into chat or commit .env to Git.
pause
notepad.exe "%~dp0.env"

findstr /B /C:"ZAPIER_WEBHOOK_URL=https://hooks.zapier.com/hooks/catch/" .env >nul
if errorlevel 1 (
  echo.
  echo The Catch Hook URL was not detected. No worker change was made.
  echo Check that the saved line starts with ZAPIER_WEBHOOK_URL=https://hooks.zapier.com/hooks/catch/
  goto done
)

docker info >nul 2>&1
if errorlevel 1 (
  echo.
  echo The hook is saved locally, but Docker Desktop is not available to restart the worker.
  echo Start Docker Desktop, then run this file again after confirming the URL is still in .env.
  goto done
)

echo.
echo Restarting the Zapier delivery worker...
docker compose up -d --no-deps --force-recreate worker
if errorlevel 1 (
  echo Worker restart failed. Review the Docker error above.
  goto done
)
echo.
echo Worker recreated. Run one approved test workflow in EnterpriseAI, then finish mapping and publish the Zap in Zapier.

:done
echo.
pause
endlocal

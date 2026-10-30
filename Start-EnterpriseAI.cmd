@echo off
setlocal
cd /d "%~dp0"
title EnterpriseAI startup

echo.
echo  EnterpriseAI - local full-stack startup
echo  =======================================
echo.

where docker >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker CLI was not found. Install or repair Docker Desktop, then try again.
  goto failed
)

docker info >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker Desktop is not ready for this Windows account.
  echo Open Docker Desktop, wait until it says Engine running, then run this file again.
  goto failed
)

docker compose config --quiet
if errorlevel 1 (
  echo ERROR: Compose configuration is invalid. Review the error above.
  goto failed
)

echo Starting the API, web console, worker, databases, Ollama, and monitoring services...
docker compose up --build -d
if errorlevel 1 goto failed

echo.
echo Downloading the default local AI models. This may take a while and several GB of disk space.
docker compose exec -T ollama ollama pull qwen2.5:7b
if errorlevel 1 goto failed
docker compose exec -T ollama ollama pull nomic-embed-text
if errorlevel 1 goto failed
docker compose exec -T ollama ollama pull llava:7b
if errorlevel 1 goto failed

echo.
echo Current service status:
docker compose ps
echo.
echo Open http://localhost:8080 and sign in with ADMIN_EMAIL and ADMIN_PASSWORD from this folder's .env file.
echo Grafana: http://localhost:3000   Prometheus: http://localhost:9090
start "" "http://localhost:8080"
echo.
echo Zapier remains disconnected until a regenerated Catch Hook URL is set as ZAPIER_WEBHOOK_URL in .env.
echo Never paste .env contents, API keys, or the private Catch Hook URL into chat or commit them to Git.
goto done

:failed
echo.
echo Startup did not finish. Copy the error text above and share that text or a Docker Desktop screenshot.

:done
echo.
pause
endlocal

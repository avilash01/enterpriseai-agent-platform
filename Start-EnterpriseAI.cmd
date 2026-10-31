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

if not exist ".env" (
  echo Creating private local credentials in .env...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$alphabet='abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'; function New-Secret([int]$size) { $bytes=New-Object byte[] $size; $rng=[System.Security.Cryptography.RandomNumberGenerator]::Create(); $rng.GetBytes($bytes); $rng.Dispose(); -join ($bytes | ForEach-Object { $alphabet[$_ % $alphabet.Length] }) }; Copy-Item '.env.example' '.env'; $content=Get-Content '.env' -Raw; $content=$content.Replace('dev-only-postgres-change-me',(New-Secret 32)).Replace('dev-only-change-to-a-random-64-character-secret-string-now',(New-Secret 64)).Replace('dev-only-admin-change-me',(New-Secret 24)).Replace('dev-only-grafana-change-me',(New-Secret 24)); Set-Content '.env' $content -NoNewline; Write-Output 'ADMIN_EMAIL=admin@enterpriseai.local'; Write-Output ('ADMIN_PASSWORD='+((Select-String '^ADMIN_PASSWORD=' '.env').Line.Split('=',2)[1])); Write-Output 'Save this password now; the generated copy is stored privately in .env.'"
  if errorlevel 1 goto failed
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

echo Pulling runtime images one at a time...
docker compose --parallel 1 pull
if errorlevel 1 goto failed

echo Building the API and web console, then starting the full stack...
docker compose --parallel 1 up --build --pull never --wait --wait-timeout 180 -d
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


# EnterpriseAI — Autonomous Multi-Agent Intelligence Platform

EnterpriseAI is a cloud-independent agent engineering project. The complete application runs on a personal computer with Docker Desktop, local Ollama models, and a private Zapier Catch Hook. The GitHub Pages site is only a static architecture preview; it cannot run the API, models, databases, worker, or live UI.

## Start the complete local application

### Requirements

- Windows 10/11 with Docker Desktop installed and the Docker Engine running.
- At least 20 GB free on the drive that stores Docker's disk image for containers and local models; additional space helps for multimodal files. If your system drive is low on space, move the Docker disk image through **Docker Desktop → Settings → Resources → Advanced → Disk image location** before starting. Never move the VHDX file by hand.
- 16 GB RAM recommended for the default 7B model. Smaller Ollama models can be selected in `.env` for less capable machines.
- Internet access for the initial container and model downloads. Agent prompts and local document embeddings then run on the PC using Ollama.

### First run

1. Open this repository folder in File Explorer and double-click `Start-EnterpriseAI.cmd`.
2. The launcher creates a private local `.env` if one does not exist, starts the Compose services, downloads the default Ollama generation, embedding, and vision models, and opens the console.
3. Sign in at [http://localhost:8080](http://localhost:8080) using the `ADMIN_EMAIL` and `ADMIN_PASSWORD` printed by the launcher once (they are also saved in the local `.env`). Keep these values private.
4. The health indicators update every 15 seconds. The first prompt may take a few minutes while Ollama loads the model.

The startup launcher validates the Docker Engine and Compose configuration, pulls runtime images one at a time, builds the API and web console, waits for the services to become healthy, then downloads models. You can also start the services manually with:

```powershell
docker compose --parallel 1 pull
docker compose --parallel 1 up --build --pull never --wait --wait-timeout 180 -d
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull llava:7b
```

Open Grafana at [http://localhost:3000](http://localhost:3000) and Prometheus at [http://localhost:9090](http://localhost:9090). The API metrics endpoint is `/metrics`.

## Functional platform

- **30 LangGraph agents:** each has a named responsibility and input/output contract. The graph executes all 30 nodes per run, using deterministic retrieval and validation tools plus model-assisted analysis and review.
- **Hybrid GraphRAG:** Ollama embeddings and Qdrant vector search, lexical overlap, FalkorDB entity relationships and graph expansion, followed by rank fusion and cited evidence.
- **Multimodal knowledge:** PDF, DOCX, text, Markdown, CSV, JSON, images, audio, and video ingestion. Vision uses Ollama; transcription uses local Whisper; video ingestion samples audio and frames.
- **API and state:** FastAPI, PostgreSQL account/run/document/evaluation/audit records, JWT sessions, Argon2 password hashes, and role-based controls for admin, editor, auditor, and viewer.
- **Zapier handoff:** explicit user approval → Redis Streams consumer group → bounded retry/backoff → dead-letter stream. The worker sends an event to your Catch Hook only after approval.
- **Operations:** health checks, Prometheus metrics, Grafana dashboards, persistent Docker volumes, and backend tests run during the image build.

## Connect Zapier

The application code and event worker are integrated; connecting a Zap requires the private Catch Hook URL from your Zapier workspace and publishing your own Zap.

1. In Zapier, use **Webhooks by Zapier → Catch Hook**. Add **Gmail → Send Email** or another action, and authenticate the app from Zapier's own sign-in flow.
2. Send a test request through the Catch Hook, select the received sample in the Gmail step, and map the `request`, `answer`, and `run_id` values into the email fields. Set the recipient explicitly in Gmail's **To** field. Test and publish the Zap.
3. In the project folder, double-click `Connect-Zapier.cmd`. Paste the private Catch Hook URL into the indicated local `.env` field, save, and close Notepad. The helper restarts the worker without displaying the URL.
4. Restart the application if needed. Check **Integrations → Service health** for `zapier_webhook_configured`. On the Overview page, check **Send prompt and final answer to Zapier after run** only when you want that content forwarded.

Never share the Catch Hook URL or commit `.env`. A previously shared webhook URL or API key should be regenerated. Zapier may have plan limits on task volume and connected apps; check your workspace's own plan. No Zapier credentials are stored by EnterpriseAI.

## No-cost public access (temporary)

There is no no-cost way to keep this full local-model stack online 24/7 on a hosted server. GitHub Pages only serves static files. Free compute plans do not provide a dependable persistent machine with the memory, model storage, and running Docker services required here.

If you need to show the running app to someone temporarily, start the local stack first and run `Start-EnterpriseAI-PublicPreview.cmd`. It opens a Cloudflare Quick Tunnel URL. This is a temporary random URL; it stops when the tunnel process or PC stops, can change on restart, has no uptime guarantee, and is not a permanent deployment. Keep your workspace credentials private. The UI uses a completed-run request through the tunnel because Quick Tunnels do not support server-sent event progress; on localhost, you get live per-agent progress.

## Troubleshooting

- **Docker engine unavailable:** open Docker Desktop, wait until it reports that the engine is running, then run `Start-EnterpriseAI.cmd` again. If Docker reports access denied, restart Docker Desktop under the same Windows account that launches the project.
- **Read-only Docker image store or failed layer write:** check free space on the host drive used by Docker's disk image. Move that image using **Settings → Resources → Advanced → Disk image location**, then restart Docker Desktop. Do not use **Clean up data** or **Reset to factory defaults** as a first step; those can remove local images and containers.
- **A browser reports connection refused:** confirm the launcher completed and `docker compose ps` shows `web`, `api`, databases, Redis, and Ollama running. Open `http://localhost:8080` (not the GitHub Pages preview).
- **Login fails:** use the local credentials from `.env`. If the database was already initialized with different credentials, update the password through the admin account or reset only after backing up your persistent data.
- **Model is unavailable:** keep Ollama running and pull the configured model. To reduce local hardware needs, choose a smaller Ollama model and pull it; keep `EMBEDDING_MODEL` available for indexing and retrieval.
- **Zapier is not receiving events:** ensure the Catch Hook is published and correctly set in `.env`, run `Connect-Zapier.cmd`, then check the worker logs with `docker compose logs -f worker`. Check failed deliveries in the dead-letter stream before retrying.
- **GitHub Pages login says API offline:** that is expected for the static preview. Run the local stack and use the localhost address for the complete application.

## Repository layout

```text
src/                     React + TypeScript workspace UI
backend/main.py          FastAPI routes, authentication, workflow API
backend/agent_workflow.py 30-node LangGraph and agent contracts
backend/enterprise_platform.py PostgreSQL, Qdrant, FalkorDB, Ollama helpers
backend/worker.py        Redis Streams → Zapier worker
ops/                     Prometheus and Grafana configuration
docker-compose.yml       Complete local service stack
```


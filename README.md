# EnterpriseAI — Autonomous Multi-Agent Intelligence Platform

EnterpriseAI is a cloud-independent, locally runnable AI agent platform. Its production path uses eight cooperating LangGraph agents, hybrid vector and knowledge-graph retrieval, multimodal ingestion, durable workflow events, approval-gated automations, RBAC, audit history, and service telemetry.

## Full local stack

Docker Compose starts the React/TypeScript console, FastAPI API, LangGraph agent workflow, Zapier delivery worker, PostgreSQL, Qdrant, Neo4j, RabbitMQ, Redis, Ollama, Prometheus, and Grafana as one stack. No paid model key or cloud account is required for local AI runs.

1. Install Docker Desktop and copy `.env.example` to `.env`. Change the development passwords and secrets before exposing any port.
2. On Windows, double-click `Start-EnterpriseAI.cmd`. It starts the stack, downloads the local AI models, displays service status, and opens the console. Or run `docker compose up --build -d` manually.
3. If starting manually, pull the Ollama models:

   ```sh
   docker compose exec ollama ollama pull qwen2.5:7b
   docker compose exec ollama ollama pull nomic-embed-text
   docker compose exec ollama ollama pull llava:7b
   ```

   Model downloads take time and several GB of disk space.
4. Open http://localhost:8080 and sign in with `ADMIN_EMAIL` and `ADMIN_PASSWORD` from `.env`.
5. Open Grafana at http://localhost:3000. Prometheus scrapes the API at `/metrics`.

Ollama serves local generation and embeddings. The eight-agent graph shares state across intake planning, research, retrieval, analysis, drafting, review, decision, and automation planning. To use a different local model, change `LLM_MODEL` and pull it into Ollama first.

## Knowledge and multimodal processing

Upload PDF, DOCX, text, Markdown, CSV, JSON, images, audio, and video from the Knowledge Base page. Text is parsed and chunked, embedded by Ollama, indexed in Qdrant, and linked to extracted entities in Neo4j. Retrieval combines vector similarity, lexical relevance, graph expansion, and a weighted reranking step. Redis caches retrieval results. PostgreSQL stores document metadata, user accounts, agent runs, citations, and audit events.

Image captions use the local Ollama vision model. Audio and video transcripts use local Whisper; video processing samples frames and extracts the audio track. The first Whisper inference downloads its model into the API container, so allow time and disk space for that initial run.

## Zapier automation and human approval

Approved workflow actions are persisted in RabbitMQ before delivery to the Zapier Catch Hook. The worker retries transient delivery failures with backoff and moves events that exhaust five retries into `enterpriseai.events.dead`. The API rejects actions without explicit human approval. The Catch Hook URL stays in the worker environment and is never placed in frontend code.

1. In Zapier, create a Zap with **Webhooks by Zapier → Catch Hook**, then add **Gmail → Send Email** (or another action). Connect Gmail using Google's sign-in and consent flow.
2. Regenerate any Catch Hook URL previously shared in chat, then set the new URL as `ZAPIER_WEBHOOK_URL` in the project-local `.env`. Keep it private.
3. On Windows, run `Connect-Zapier.cmd`. It opens `.env` locally and recreates the worker after you save it. It does not print the URL.
4. Run an agent prompt with the Zapier approval checkbox checked. The approval explicitly authorizes forwarding that prompt and final answer. This first live run sends a sample event to Zapier so you can map the `request` and `answer` fields into the Gmail action.
5. Test the Gmail action and publish the Zap in Zapier. Only then will the external automation be active.

Each approved event carries the run ID, agent names, timestamp, prompt, answer, and approved action payload. The approval is recorded in the audit log. Unchecked runs do not send events. Never commit `.env` or paste API keys and private hook URLs into chat.

## Security and observability

- JWT login backed by PostgreSQL; supported roles are `admin`, `editor`, `auditor`, and `viewer`.
- Document ingestion requires `admin` or `editor`; audit history requires `admin` or `auditor`.
- Argon2 password hashing; JWT secret is required and must be rotated for deployment.
- Audit records cover sign-ins, agent runs, document ingestion, and approved actions.
- Prometheus metrics are exposed at `/metrics`; Grafana provisions the Prometheus data source.
- Health checks gate service startup. Compose persists PostgreSQL, Qdrant, Neo4j, RabbitMQ, Redis, Ollama, Prometheus, and Grafana state in named volumes.

The default model provider is local Ollama and needs no external LLM API key. For optional Groq comparison, set `LLM_PROVIDER=groq`, choose a supported Groq model in `LLM_MODEL`, and add a newly rotated `GROQ_API_KEY` to the API service environment. Never commit it or place it in frontend variables.

## Hosted deployment

GitHub Pages hosts the architecture preview only. It does not run the API, agent models, databases, queue, or Zapier worker. The full Compose stack requires a persistent Docker host with disk space for model downloads and databases. The production overlay adds Caddy for automatic HTTPS; only Caddy's web ports are public. Data services stay on the private Compose network.

1. Copy `.env.example` to `.env`. Replace every development password and the JWT secret. Set `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `DOMAIN`, `CORS_ORIGINS=https://your-domain`, and the regenerated private `ZAPIER_WEBHOOK_URL`.
2. Point your domain DNS A record at the Docker host and allow TCP ports 80 and 443 through its firewall.
3. Start the stack with `docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d`.
4. Pull `qwen2.5:7b`, `nomic-embed-text`, and `llava:7b` into Ollama.
5. Open `https://your-domain` and sign in with the admin credentials from `.env`.
6. Test the Catch Hook with a live approved run, map `request` and `answer` in Gmail, then publish the Zap.

A hosted Docker VM may incur ongoing charges. No VM or paid service is provisioned by this repository. Do not expose database, vector, graph, queue, cache, or Ollama ports to the public internet.

## Engineering status

The repository includes the full local Compose architecture and integration points. A Zapier account owner must provide a regenerated private Catch Hook URL, finish the Gmail mapping, and publish their Zap. Service checks and dashboard activity are read from the API; no sample run metrics are presented as live activity.

# EnterpriseAI — Autonomous Multi-Agent Intelligence Platform

EnterpriseAI is a cloud-independent, locally runnable AI agent platform. Its production path uses eight cooperating LangGraph agents, hybrid vector and knowledge-graph retrieval, multimodal ingestion, durable workflow events, approval-gated automations, RBAC, audit history, and service telemetry.

## Full local stack

Docker Compose starts the React/TypeScript console, FastAPI API, LangGraph agent workflow, Zapier delivery worker, PostgreSQL, Qdrant, Neo4j, RabbitMQ, Redis, Ollama, Prometheus, and Grafana as one stack. No paid model key or cloud account is required for local AI runs.

1. Install Docker Desktop and copy `.env.example` to `.env`. Change all development passwords and secrets before exposing any port.
2. Start the complete stack: `docker compose up --build -d`.
3. Pull the local models into Ollama:

   ```sh
   docker compose exec ollama ollama pull qwen2.5:7b
   docker compose exec ollama ollama pull nomic-embed-text
   docker compose exec ollama ollama pull llava:7b
   ```

4. Open the console at http://localhost:8080 and sign in with the `ADMIN_EMAIL` and `ADMIN_PASSWORD` from `.env`.
5. Open Grafana at http://localhost:3000. Prometheus scrapes the API at `/metrics`.

Ollama serves local generation and embeddings. The eight-agent graph shares its state across intake planning, research, retrieval, analysis, drafting, review, decision, and automation planning. To use a different local model, change `LLM_MODEL` and pull it into Ollama first.

## Knowledge and multimodal processing

Upload PDF, DOCX, text, Markdown, CSV, JSON, images, audio, and video from the Knowledge Base page. Text is parsed and chunked, embedded by Ollama, indexed in Qdrant, and linked to extracted entities in Neo4j. Retrieval combines vector similarity, lexical relevance, graph expansion, and a weighted reranking step. Redis caches retrieval results. PostgreSQL stores document metadata, user accounts, agent runs, citations, and audit events.

Image captions use the local Ollama vision model. Audio and video transcripts use local Whisper; video processing samples frames and extracts the audio track. The first Whisper inference downloads its model into the API container, so allow time and disk space for that initial run.

## Automation and human approval

Approved workflow actions are persisted in RabbitMQ before delivery to the Zapier Catch Hook. The worker retries transient delivery failures with backoff and moves events that exhaust five retries into `enterpriseai.events.dead`. The API rejects actions without explicit human approval. Configure the Zapier hook URL in `.env` before using the automation handoff. Keep the hook URL private; it is a credential and never belongs in frontend code.

Create a Zap with **Webhooks by Zapier → Catch Hook**, then add **Gmail → Send Email** (or another action). Connect Gmail in Zapier with Google's sign-in and consent flow. Copy the private Catch Hook URL into `ZAPIER_WEBHOOK_URL` in `.env`, restart the worker with `docker compose up -d worker`, then run an agent prompt with the Zapier approval box checked. After the first event arrives, map the `request` and `answer` fields into the Gmail message. The approval box explicitly authorizes forwarding that prompt and final answer; without it, no event is sent. Each forwarded event also carries the run ID, agent names, timestamp, and any approved action payload. The approval is recorded in the audit log.

## Security and observability

- JWT login backed by PostgreSQL; supported roles are `admin`, `editor`, `auditor`, and `viewer`.
- Document ingestion requires `admin` or `editor`; audit history requires `admin` or `auditor`.
- Argon2 password hashing; JWT secret is required and must be rotated for deployment.
- Audit records cover sign-ins, agent runs, document ingestion, and approved actions.
- Prometheus metrics are exposed at `/metrics`; Grafana provisions the Prometheus data source.
- Health checks gate service startup. Compose persists PostgreSQL, Qdrant, Neo4j, RabbitMQ, Redis, Ollama, Prometheus, and Grafana state in named volumes.

For a different model provider, set `LLM_PROVIDER=groq`, choose a supported Groq model in `LLM_MODEL`, and supply a **rotated** `GROQ_API_KEY` through the API service's secret environment. Never commit `.env` or place model credentials in frontend variables.

## Hosted deployment

GitHub Pages hosts an architecture preview only. It does not run the API, agent models, databases, queue, or Zapier worker. For a complete deployment, use a Linux Docker host with persistent disk, a DNS name pointing to that host, and inbound TCP ports 80 and 443 open. The production overlay adds Caddy for automatic HTTPS; only Caddy's web ports are public. Data services remain on the private Compose network.

1. Copy `.env.example` to `.env`. Replace every development password and the JWT secret with unique random values. Set `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and `DOMAIN` to your values. Set `CORS_ORIGINS=https://your-domain` and `ZAPIER_WEBHOOK_URL` to the regenerated private Catch Hook URL. Do not commit `.env`.
2. Point your domain's DNS A record at the host and allow TCP ports 80 and 443 through its firewall.
3. Start the complete stack from the repository directory: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d`.
4. Pull the local models: `docker compose exec ollama ollama pull qwen2.5:7b`, then pull `nomic-embed-text` and `llava:7b`. The first model downloads need time and persistent disk space.
5. Open `https://your-domain` and sign in with the admin credentials from `.env`. The frontend uses same-origin `/api` requests through Nginx; no frontend API secret or public database port is needed.
6. In Zapier, test the Catch Hook with a live approved agent run. Map its `request` and `answer` fields in **Gmail → Send Email**, test the action, then publish the Zap. Each checked approval forwards the prompt and final answer; unchecked runs never send them.

If deploying without a DNS name, use the local Compose instructions instead of the production HTTPS overlay. Do not expose database, vector, graph, queue, cache, or Ollama ports to the public internet.

## Engineering status

The project contains implementations and Compose services for the capabilities in the project brief. Zapier needs the workspace's private Catch Hook URL and downstream app credentials. Dashboard counts and service checks come from the API; no sample run metrics are presented as real activity.

# EnterpriseAI — Autonomous Multi-Agent Intelligence Platform

EnterpriseAI is a cloud-independent, locally runnable AI agent platform. Its production path uses eight cooperating LangGraph agents, hybrid vector and knowledge-graph retrieval, multimodal ingestion, durable workflow events, approval-gated automations, RBAC, audit history, and service telemetry.

## Full local stack

Docker Compose starts the React/TypeScript console, FastAPI API, LangGraph worker API, PostgreSQL, Qdrant, Neo4j, RabbitMQ, Redis, Ollama, n8n, Prometheus, and Grafana as one stack. No paid model key or cloud account is required.

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

Approved workflow actions are persisted in RabbitMQ before delivery. The worker forwards events to the configured n8n webhook and Zapier Catch Hook, retries transient delivery failures with backoff, and moves events that exhaust five retries into `enterpriseai.events.dead`. The API rejects actions without explicit human approval. At least one destination URL must be configured before automation approval is accepted. Keep webhook URLs private and set them in the worker environment, never in frontend code.

To connect n8n, import `ops/n8n/enterpriseai-approved-events.json`, activate it, and set `N8N_WEBHOOK_URL=http://n8n:5678/webhook/enterpriseai-approved-events` in `.env`. This internal Docker hostname is used by the worker. Add downstream Slack, email, or CRM nodes and their credentials in n8n. To connect Zapier, create a Webhooks by Zapier Catch Hook and set its HTTPS URL as `ZAPIER_WEBHOOK_URL`. Events carry the run ID, agent names, time, and explicitly approved action payload.

## Security and observability

- JWT login backed by PostgreSQL; supported roles are `admin`, `editor`, `auditor`, and `viewer`.
- Document ingestion requires `admin` or `editor`; audit history requires `admin` or `auditor`.
- Argon2 password hashing; JWT secret is required and must be rotated for deployment.
- Audit records cover sign-ins, agent runs, document ingestion, and approved actions.
- Prometheus metrics are exposed at `/metrics`; Grafana provisions the Prometheus data source.
- Health checks gate service startup. Compose persists PostgreSQL, Qdrant, Neo4j, RabbitMQ, Redis, Ollama, n8n, Prometheus, and Grafana state in named volumes.

For a different model provider, set `LLM_PROVIDER=groq`, choose a supported Groq model in `LLM_MODEL`, and supply a **rotated** `GROQ_API_KEY` through the API service's secret environment. Never commit `.env` or place model credentials in frontend variables.

## Hosted deployment

The public GitHub Pages URL hosts the static console preview. The complete backend and data plane run through Docker Compose; they are not hosted by GitHub Pages. To make the public UI use a hosted API, deploy the entire Compose stack on a Docker host, set its secure service secrets, and set `VITE_API_BASE_URL` at frontend build time to the API origin. Do not expose database, vector, graph, queue, cache, or model ports to the public internet.

## Engineering status

The project now contains implementations and Compose services for each capability in the project brief. Third-party automations still need their destination URLs and app credentials configured by the workspace owner. Dashboard analytics use API-backed service status where available; historical charts are illustrative until real aggregate telemetry is wired to their queries.

# EnterpriseAI — Autonomous Multi-Agent Intelligence Platform

A cloud-independent agent operations platform using Google's Agent Development Kit (ADK), FastAPI, and a local-first model connection. The API runs eight specialists in a deterministic sequence: intake planner → research analyst → knowledge retriever → analysis → writing → quality review → decision → automation planner. ADK is used as a Python library; the app does not require Google Cloud. LiteLLM connects ADK to Ollama or Groq.

## Run locally

1. Install [Ollama](https://ollama.com/) and pull a tool-capable model, for example `ollama pull llama3.2`.
2. Copy `.env.example` to `.env`.
3. Run `docker compose up --build` and open http://localhost:8080.

On Windows and macOS, the container reaches Ollama through `host.docker.internal`. To use Groq, set `LLM_PROVIDER=groq`, set `LLM_MODEL=llama-3.3-70b-versatile` (or another current Groq model), and add a **rotated** `GROQ_API_KEY` to `.env`. Never commit `.env`; configure provider secrets in the deployment host's secret manager.

## Zapier automation

Create a Zap with **Webhooks by Zapier → Catch Hook**, then put its hook URL in the backend-only `ZAPIER_WEBHOOK_URL` setting. Keep that URL private; it is a credential. The dashboard checkbox explicitly approves sending an `enterpriseai.run.completed` event. The payload includes the run ID, eight agent names, and timestamp; it does not include the user's prompt or answer. Map the hook fields to any Zap actions you choose, such as a Slack message, email, or CRM update. If no hook URL is configured, chat still works and the API reports `not_configured`.

## Architecture status

- **Implemented:** React operations console; FastAPI; Google ADK sequential orchestration; eight specialist agents; LiteLLM model adapter; Ollama and Groq configuration; opt-in Zapier run-completed webhook; Docker Compose.
- **Shown as planned in the Architecture page:** document ingestion, Qdrant vector search, Neo4j entity graph, reranking, Redis/PostgreSQL durable memory, RBAC, and production telemetry/evaluation. Those services are not implemented yet.
- Dashboard KPIs, charts, and fleet status remain demo data. The GitHub Pages deployment is a static UI preview; the FastAPI service must run on a backend host before the hosted chat can reach it.

For frontend development without Docker, run `npm install` then `npm run dev`; the Vite proxy forwards `/api` to `localhost:8000`. Start the API with `python -m venv .venv`, activate it, `pip install -r backend/requirements.txt`, then `uvicorn main:app --app-dir backend --reload --port 8000`.

## Architecture and roadmap

- React + TypeScript dashboard and FastAPI API.
- Ollama-compatible local inference by default; Groq API is optional and secrets stay in the backend environment.
- Docker Compose deployment, independent of a cloud vendor.
- Next slices: LangGraph orchestration and durable run state; document ingestion and hybrid retrieval; approval-gated tools; evaluation, audit records, RBAC, and service monitoring.

The screenshots are visual references. Current charts, statuses, graph nodes, and KPI values are demonstration data and should not be interpreted as telemetry from a live system.

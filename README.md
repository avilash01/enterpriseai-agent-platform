# EnterpriseAI — Autonomous Multi-Agent Intelligence Platform

A cloud-independent agent operations dashboard with a FastAPI service and a local-first model connection. The first vertical slice includes an operations UI, agent fleet view, orchestration graph, and a server-side LLM request path. The graph and operational metrics are currently illustrative UI data; the first API implementation provides a single model-backed assistant request, not a deployed multi-agent or RAG runtime.

## Run locally

1. Install [Ollama](https://ollama.com/) and pull a model, for example `ollama pull llama3.2`.
2. Copy `.env.example` to `.env`.
3. Run `docker compose up --build` and open http://localhost:8080.

On Windows and macOS, the container reaches Ollama through `host.docker.internal`. To use Groq, set `LLM_PROVIDER=groq`, set `LLM_MODEL` to a currently available Groq model, and add `GROQ_API_KEY` to `.env`. Never commit `.env`; configure provider secrets in the deployment host's secret manager. Rotate any key shared in chat before using it.

For frontend development without Docker, run `npm install` then `npm run dev`; the Vite proxy forwards `/api` to `localhost:8000`. Start the API with `python -m venv .venv`, activate it, `pip install -r backend/requirements.txt`, then `uvicorn main:app --app-dir backend --reload --port 8000`.

## Architecture and roadmap

- React + TypeScript dashboard and FastAPI API.
- Ollama-compatible local inference by default; Groq API is optional and secrets stay in the backend environment.
- Docker Compose deployment, independent of a cloud vendor.
- Next slices: LangGraph orchestration and durable run state; document ingestion and hybrid retrieval; approval-gated tools; evaluation, audit records, RBAC, and service monitoring.

The screenshots are visual references. Current charts, statuses, graph nodes, and KPI values are demonstration data and should not be interpreted as telemetry from a live system.

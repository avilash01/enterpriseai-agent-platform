import json
import os
import asyncio
import uuid
from datetime import datetime, timezone
import urllib.error
import urllib.request
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from agent_workflow import build_workflow

app = FastAPI(title="EnterpriseAI API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","), allow_methods=["*"], allow_headers=["*"])

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    notify_zapier: bool = False
    zapier_approved: bool = False

@app.get("/api/health")
def health():
    return {"status": "ok", "provider": os.getenv("LLM_PROVIDER", "ollama"), "model": os.getenv("LLM_MODEL", "llama3.2"), "agent_framework": "google-adk", "zapier_configured": bool(os.getenv("ZAPIER_WEBHOOK_URL"))}

@app.post("/api/chat")
async def chat(body: ChatRequest):
    if body.notify_zapier and not body.zapier_approved:
        raise HTTPException(400, "Explicit approval is required before sending a run event to Zapier.")
    try:
        agent = build_workflow()
        session_service = InMemorySessionService()
        runner = Runner(agent=agent, app_name="enterpriseai", session_service=session_service)
        user_id = "dashboard-user"
        session = await session_service.create_session(app_name="enterpriseai", user_id=user_id)
        answer = ""
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=body.message)]),
        ):
            if event.is_final_response() and event.content and event.content.parts:
                answer = "\n".join(part.text for part in event.content.parts if part.text)
        if not answer:
            raise HTTPException(502, "The agent workflow completed without a final answer.")
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        raise HTTPException(502, f"Agent workflow failed: {exc}")

    automation_status = "not_requested"
    if body.notify_zapier:
        run_id = str(uuid.uuid4())
        automation_status = await asyncio.to_thread(_send_zapier_event, run_id)
    else:
        run_id = str(uuid.uuid4())
    return {"answer": answer, "provider": os.getenv("LLM_PROVIDER", "ollama"), "model": os.getenv("LLM_MODEL", "llama3.2"), "framework": "google-adk", "agents": ["research_agent", "analysis_agent", "writing_agent", "quality_reviewer"], "run_id": run_id, "zapier_status": automation_status}

def _send_zapier_event(run_id: str) -> str:
    webhook_url = os.getenv("ZAPIER_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return "not_configured"
    if not webhook_url.startswith("https://hooks.zapier.com/"):
        return "invalid_configuration"
    # Send run metadata only; never forward the prompt or model response by default.
    event = {"event": "enterpriseai.run.completed", "run_id": run_id, "agent_framework": "google-adk", "agents": ["research_agent", "analysis_agent", "writing_agent", "quality_reviewer"], "occurred_at": datetime.now(timezone.utc).isoformat()}
    request = urllib.request.Request(webhook_url, data=json.dumps(event).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return "sent" if 200 <= response.status < 300 else "failed"
    except (urllib.error.URLError, TimeoutError):
        return "failed"

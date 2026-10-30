import json
import os
import urllib.error
import urllib.request
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="EnterpriseAI API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","), allow_methods=["*"], allow_headers=["*"])

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)

@app.get("/api/health")
def health():
    return {"status": "ok", "provider": os.getenv("LLM_PROVIDER", "ollama"), "model": os.getenv("LLM_MODEL", "llama3.2")}

@app.post("/api/chat")
def chat(body: ChatRequest):
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider == "groq":
        base_url = "https://api.groq.com/openai/v1"
        api_key = os.getenv("GROQ_API_KEY")
        model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        if not api_key:
            raise HTTPException(503, "Set GROQ_API_KEY in the server environment.")
    else:
        base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
        api_key = os.getenv("LLM_API_KEY", "ollama")
        model = os.getenv("LLM_MODEL", "llama3.2")
    payload = json.dumps({"model": model, "messages": [{"role": "system", "content": "You are EnterpriseAI, a careful enterprise research assistant. Be concise, distinguish evidence from inference, and never claim to have accessed knowledge sources or executed actions that were not provided."}, {"role": "user", "content": body.message}], "temperature": 0.3}).encode()
    req = urllib.request.Request(f"{base_url.rstrip('/')}/chat/completions", data=payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            data = json.loads(response.read())
        return {"answer": data["choices"][0]["message"]["content"], "model": model, "provider": provider}
    except urllib.error.HTTPError as exc:
        details = exc.read().decode(errors="replace")[:500]
        raise HTTPException(exc.code if exc.code < 500 else 502, f"LLM provider error: {details}")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise HTTPException(502, f"Could not reach {provider} provider: {exc}")

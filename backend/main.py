"""EnterpriseAI API: authenticated runs, knowledge ingestion, workflow approvals and telemetry."""
from __future__ import annotations
import asyncio, json, os, uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import select
import httpx
from agent_workflow import AGENT_CATALOG, AGENT_NAMES, build_workflow, evaluate_run
from enterprise_platform import (AuditEvent, EvaluationRecord, KnowledgeDocument, RunRecord, SessionLocal, User, audit, decode_token,
                      extract_file, graph_expand, hybrid_retrieve, index_text, initialize_database, make_token, password_hash, persist_run_entities, publish_event)

app=FastAPI(title="EnterpriseAI Autonomous Multi-Agent Intelligence Platform",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=os.getenv("CORS_ORIGINS","http://localhost:8080,http://localhost:5173,https://avilash01.github.io").split(","),allow_methods=["*"],allow_headers=["*"])
Instrumentator().instrument(app).expose(app,endpoint="/metrics",include_in_schema=False)
bearer=HTTPBearer(auto_error=False)

@app.on_event("startup")
def startup(): initialize_database()

def current_user(credentials: Annotated[HTTPAuthorizationCredentials|None,Depends(bearer)]):
    if not credentials: raise HTTPException(401,"Sign in to use EnterpriseAI")
    claims=decode_token(credentials.credentials)
    if not claims: raise HTTPException(401,"Session expired. Sign in again.")
    with SessionLocal() as db: user=db.get(User,claims.get("sub"))
    if not user or not user.active: raise HTTPException(401,"Account is disabled")
    return {"id":user.id,"email":user.email,"role":user.role}
def require_roles(*roles):
    def dependency(user=Depends(current_user)):
        if user["role"] not in roles: raise HTTPException(403,"Your role cannot perform this action")
        return user
    return dependency

class LoginRequest(BaseModel): email:str; password:str
class UserCreate(BaseModel): email:str; password:str=Field(min_length=12); role:str=Field(pattern="^(admin|editor|auditor|viewer)$")
class EvaluationRequest(BaseModel): question:str=Field(min_length=1,max_length=12000)
class ChatRequest(BaseModel): message:str=Field(min_length=1,max_length=12000); attachments:list[str]=Field(default_factory=list); approve_automation:bool=False; automation_payload:dict=Field(default_factory=dict)
class ActionRequest(BaseModel): action:str=Field(min_length=1,max_length=100); payload:dict=Field(default_factory=dict); approved:bool=False

def _db_check():
    from sqlalchemy import text
    with SessionLocal() as db: db.execute(text("SELECT 1"))
    return True
def _redis_check():
    from redis import Redis
    return bool(Redis.from_url(os.getenv("REDIS_URL","redis://redis:6379/0"),socket_timeout=2).ping())
def _falkor_check():
    from enterprise_platform import _falkor_graph
    return bool(_falkor_graph().query("RETURN 1").result_set)
async def _health_checks():
    checks={}
    for key, fn in [("postgresql",_db_check),("redis",_redis_check),("falkordb",_falkor_check)]:
        try: checks[key]=bool(await asyncio.wait_for(asyncio.to_thread(fn),timeout=4))
        except Exception: checks[key]=False
    async with httpx.AsyncClient(timeout=2) as client:
        for key,url in [("qdrant","http://qdrant:6333/collections"),("ollama","http://ollama:11434/api/tags"),("prometheus","http://prometheus:9090/-/healthy"),("grafana","http://grafana:3000/api/health")]:
            try:
                response=await client.get(url); checks[key]=response.status_code==200
                if key=="ollama" and checks[key]:
                    names={m.get("name","").split(":")[0] for m in response.json().get("models",[])}
                    checks["model_ready"]=(bool(os.getenv("GROQ_API_KEY")) if os.getenv("LLM_PROVIDER","ollama").lower()=="groq" else os.getenv("LLM_MODEL","qwen2.5:7b").split(":")[0] in names)
                    checks["embedding_model_ready"]=os.getenv("EMBEDDING_MODEL","nomic-embed-text").split(":")[0] in names
            except Exception:
                checks[key]=False
                if key=="ollama" and os.getenv("LLM_PROVIDER","ollama").lower()=="groq":
                    checks["model_ready"]=bool(os.getenv("GROQ_API_KEY"))
                    checks["embedding_model_ready"]=False
    checks["zapier_webhook_configured"]=bool(os.getenv("ZAPIER_WEBHOOK_URL"))
    checks["redis_stream_ready"]=checks.get("redis",False)
    if os.getenv("LLM_PROVIDER","ollama").lower()=="groq":
        core=["postgresql","qdrant","falkordb","redis","model_ready","embedding_model_ready"]
    else:
        core=["postgresql","qdrant","falkordb","redis","ollama","model_ready","embedding_model_ready"]
    return {"status":"ok" if all(checks.get(name) for name in core) else "degraded","checks":checks}

@app.get("/api/health")
async def health():
    details=await _health_checks()
    return {**details,"provider":os.getenv("LLM_PROVIDER","ollama"),"model":os.getenv("LLM_MODEL","qwen2.5:7b"),"agent_framework":"langgraph","agent_count":len(AGENT_NAMES),"services":list(details["checks"].keys())}

@app.post("/api/auth/login")
def login(body:LoginRequest):
    with SessionLocal() as db: user=db.scalar(select(User).where(User.email==body.email.lower()))
    if not user or not user.active or not password_hash.verify(body.password,user.password_hash): raise HTTPException(401,"Email or password is incorrect")
    audit(user.id,"auth.login","session")
    return {"access_token":make_token(user),"token_type":"bearer","user":{"id":user.id,"email":user.email,"role":user.role}}

@app.get("/api/auth/me")
def me(user=Depends(current_user)): return user

@app.get("/api/agents")
def agents(user=Depends(current_user)):
    return {"framework":"langgraph","agents":[{**agent.__dict__,"status":"ready"} for agent in AGENT_CATALOG]}

@app.get("/api/users")
def users(user=Depends(require_roles("admin"))):
    with SessionLocal() as db: items=db.scalars(select(User).order_by(User.email)).all()
    return {"items":[{"id":u.id,"email":u.email,"role":u.role,"active":u.active} for u in items]}

@app.post("/api/users",status_code=201)
def create_user(body:UserCreate,user=Depends(require_roles("admin"))):
    with SessionLocal.begin() as db:
        if db.scalar(select(User).where(User.email==body.email.lower())): raise HTTPException(409,"An account with that email already exists")
        created=User(email=body.email.lower(),password_hash=password_hash.hash(body.password),role=body.role); db.add(created); db.flush()
        response={"id":created.id,"email":created.email,"role":created.role,"active":created.active}
    audit(user["id"],"user.created",response["id"],{"role":body.role})
    return response

@app.post("/api/chat")
async def chat(body:ChatRequest,user=Depends(current_user)):
    if body.approve_automation and user["role"] not in {"admin","editor"}:
        raise HTTPException(403,"Only an admin or editor can approve automation events")
    if body.approve_automation and not os.getenv("ZAPIER_WEBHOOK_URL"):
        raise HTTPException(503,"Configure ZAPIER_WEBHOOK_URL with your Zapier Catch Hook before approving automation")
    run_id=str(uuid.uuid4())
    try:
        graph=build_workflow(hybrid_retrieve,graph_expand,persist_run_entities)
        result=await graph.ainvoke({"request":body.message,"attachments":body.attachments,"run_id":run_id})
        answer=result.get("answer","")
        if not answer: raise HTTPException(502,"The agent workflow completed without a final answer")
        with SessionLocal.begin() as db: db.add(RunRecord(id=run_id,user_id=user["id"],request_hash=__import__("hashlib").sha256(body.message.encode()).hexdigest(),answer=answer,citations=json.dumps(result.get("citations",[]))))
        audit(user["id"],"agent.run.completed",run_id,{"agent_count":len(AGENT_NAMES)})
        automation_status="not_requested"
        if body.approve_automation:
            event={"event":"enterpriseai.run.completed","run_id":run_id,"agent_framework":"langgraph","agents":AGENT_NAMES,"occurred_at":datetime.now(timezone.utc).isoformat(),"request":body.message,"answer":answer,"actions":body.automation_payload}
            await publish_event(event)
            audit(user["id"],"workflow.zapier.approved",run_id,{"prompt_and_answer_forwarded":True})
            automation_status="queued_for_zapier"
        return {"answer":answer,"framework":"langgraph","agents":AGENT_NAMES,"run_id":run_id,"citations":result.get("citations",[]),"automation_status":automation_status}
    except HTTPException: raise
    except RuntimeError as exc: raise HTTPException(503,str(exc))
    except Exception as exc: raise HTTPException(502,f"Agent workflow failed: {exc}")

@app.post("/api/chat/stream")
async def chat_stream(body:ChatRequest,user=Depends(current_user)):
    if body.approve_automation and user["role"] not in {"admin","editor"}:
        raise HTTPException(403,"Only an admin or editor can approve Zapier actions")
    if body.approve_automation and not os.getenv("ZAPIER_WEBHOOK_URL"):
        raise HTTPException(503,"Configure ZAPIER_WEBHOOK_URL with your Zapier Catch Hook before approving automation")
    run_id=str(uuid.uuid4())
    try: graph=build_workflow(hybrid_retrieve,graph_expand,persist_run_entities)
    except RuntimeError as exc: raise HTTPException(503,str(exc))

    async def events():
        state={"request":body.message,"attachments":body.attachments,"run_id":run_id}
        yield "data: "+json.dumps({"type":"start","run_id":run_id,"agents":AGENT_NAMES})+"\n\n"
        try:
            async for update in graph.astream(state,stream_mode="updates"):
                for agent,values in update.items():
                    state.update(values)
                    yield "data: "+json.dumps({"type":"agent_completed","agent":agent})+"\n\n"
            answer=state.get("answer","")
            if not answer: raise RuntimeError("The agent workflow completed without a final answer")
            with SessionLocal.begin() as db:
                db.add(RunRecord(id=run_id,user_id=user["id"],request_hash=__import__("hashlib").sha256(body.message.encode()).hexdigest(),answer=answer,citations=json.dumps(state.get("citations",[]))))
            audit(user["id"],"agent.run.completed",run_id,{"agent_count":len(AGENT_NAMES)})
            automation_status="not_requested"
            if body.approve_automation:
                event={"event":"enterpriseai.run.completed","run_id":run_id,"agent_framework":"langgraph","agents":AGENT_NAMES,"occurred_at":datetime.now(timezone.utc).isoformat(),"request":body.message,"answer":answer,"actions":body.automation_payload}
                await publish_event(event)
                audit(user["id"],"workflow.zapier.approved",run_id,{"prompt_and_answer_forwarded":True})
                automation_status="queued_for_zapier"
            yield "data: "+json.dumps({"type":"done","answer":answer,"agents":AGENT_NAMES,"citations":state.get("citations",[]),"automation_status":automation_status})+"\n\n"
        except Exception as exc:
            yield "data: "+json.dumps({"type":"error","message":str(exc)})+"\n\n"
    return StreamingResponse(events(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.post("/api/knowledge/documents",status_code=201)
async def ingest_document(file:UploadFile=File(...),user=Depends(require_roles("admin","editor"))):
    data=await file.read()
    if len(data)>30*1024*1024: raise HTTPException(413,"Maximum upload size is 30 MB")
    try: text=await asyncio.to_thread(extract_file,file.filename or "upload",file.content_type or "application/octet-stream",data)
    except ValueError as exc: raise HTTPException(415,str(exc))
    except Exception as exc: raise HTTPException(422,f"Could not extract document content: {exc}")
    try: result=await asyncio.to_thread(index_text,file.filename or "Untitled",file.content_type or "application/octet-stream",text)
    except Exception as exc: raise HTTPException(503,f"Knowledge indexing failed: {exc}")
    audit(user["id"],"knowledge.document.ingested",result["id"],{"chunks":result["chunk_count"],"entities":result["entities"]})
    return result

@app.get("/api/knowledge/documents")
def documents(user=Depends(current_user)):
    with SessionLocal() as db: docs=db.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc()).limit(200)).all()
    return {"items":[{"id":d.id,"title":d.title,"media_type":d.media_type,"chunk_count":d.chunk_count,"created_at":d.created_at.isoformat()} for d in docs]}

@app.get("/api/knowledge/search")
async def search_knowledge(q:str,user=Depends(current_user)):
    if not q.strip(): raise HTTPException(400,"A search query is required")
    return {"items":await hybrid_retrieve(q.strip(),limit=10)}

@app.get("/api/runs")
def runs(user=Depends(current_user)):
    with SessionLocal() as db: items=db.scalars(select(RunRecord).where(RunRecord.user_id==user["id"]).order_by(RunRecord.created_at.desc()).limit(100)).all()
    return {"items":[{"id":r.id,"status":r.status,"answer":r.answer,"citations":json.loads(r.citations),"created_at":r.created_at.isoformat()} for r in items]}

@app.post("/api/runs/{run_id}/evaluate")
async def evaluate(run_id:str,body:EvaluationRequest,user=Depends(current_user)):
    with SessionLocal() as db: run=db.get(RunRecord,run_id)
    if not run or run.user_id!=user["id"] and user["role"]!="admin": raise HTTPException(404,"Run not found")
    try: scores=await evaluate_run(body.question,run.answer,json.loads(run.citations))
    except Exception as exc: raise HTTPException(502,f"Evaluation failed: {exc}")
    with SessionLocal.begin() as db: db.add(EvaluationRecord(run_id=run_id,user_id=user["id"],scores=json.dumps(scores)))
    audit(user["id"],"evaluation.completed",run_id)
    return {"run_id":run_id,"scores":scores}

@app.get("/api/evaluations")
def evaluations(user=Depends(current_user)):
    with SessionLocal() as db: items=db.scalars(select(EvaluationRecord).where(EvaluationRecord.user_id==user["id"]).order_by(EvaluationRecord.created_at.desc()).limit(100)).all()
    return {"items":[{"id":e.id,"run_id":e.run_id,"scores":json.loads(e.scores),"created_at":e.created_at.isoformat()} for e in items]}

@app.get("/api/audit")
def audit_log(user=Depends(require_roles("admin","auditor"))):
    with SessionLocal() as db: items=db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(200)).all()
    return {"items":[{"id":e.id,"user_id":e.user_id,"action":e.action,"resource":e.resource,"details":json.loads(e.details),"created_at":e.created_at.isoformat()} for e in items]}

@app.post("/api/workflows/actions")
async def workflow_action(body:ActionRequest,user=Depends(require_roles("admin","editor"))):
    if not body.approved: raise HTTPException(409,"Human approval is required before workflow execution")
    if not os.getenv("ZAPIER_WEBHOOK_URL"):
        raise HTTPException(503,"Configure ZAPIER_WEBHOOK_URL with your Zapier Catch Hook before approving automation")
    event={"event":"enterpriseai.workflow.approved","run_id":str(uuid.uuid4()),"user_id":user["id"],"action":body.action,"payload":body.payload,"approved_at":datetime.now(timezone.utc).isoformat()}
    await publish_event(event); audit(user["id"],"workflow.action.approved",body.action)
    return {"status":"queued","event":event["event"]}



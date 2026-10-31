"""Knowledge ingestion, hybrid retrieval, persistence, authorization, and queue helpers."""
from __future__ import annotations
import asyncio, glob, hashlib, io, json, os, re, uuid, subprocess, tempfile
from datetime import datetime, timezone, timedelta

import httpx
import requests
from jose import JWTError, jwt
from pwdlib import PasswordHash
from qdrant_client import QdrantClient, models
from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://enterpriseai:enterpriseai@postgres:5432/enterpriseai")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(String(30), default="viewer")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    media_type: Mapped[str] = mapped_column(String(100))
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class RunRecord(Base):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String(30), default="completed")
    request_hash: Mapped[str] = mapped_column(String(64))
    answer: Mapped[str] = mapped_column(Text)
    citations: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class EvaluationRecord(Base):
    __tablename__ = "evaluations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    scores: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, index=True)
    action: Mapped[str] = mapped_column(String(100))
    resource: Mapped[str] = mapped_column(String(200))
    details: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

password_hash = PasswordHash.recommended()
def initialize_database():
    Base.metadata.create_all(engine)
    admin_email = os.getenv("ADMIN_EMAIL", "admin@enterpriseai.local").lower()
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    with SessionLocal.begin() as db:
        if admin_password and not db.scalar(select(User).where(User.email == admin_email)):
            db.add(User(email=admin_email, password_hash=password_hash.hash(admin_password), role="admin"))

def make_token(user: User):
    secret = os.getenv("JWT_SECRET", "")
    if len(secret) < 32: raise RuntimeError("JWT_SECRET must contain at least 32 characters")
    return jwt.encode({"sub": user.id, "email": user.email, "role": user.role,"exp":datetime.now(timezone.utc)+timedelta(hours=12)}, secret, algorithm="HS256")
def decode_token(token: str):
    try: return jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
    except (JWTError, KeyError): return None
def audit(user_id: str, action: str, resource: str, details: dict | None = None):
    with SessionLocal.begin() as db: db.add(AuditEvent(user_id=user_id, action=action, resource=resource, details=json.dumps(details or {})))

def _qdrant(): return QdrantClient(url=os.getenv("QDRANT_URL", "http://qdrant:6333"))
def _embed(texts: list[str]):
    response = requests.post(os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")+"/api/embed", json={"model": os.getenv("EMBEDDING_MODEL", "nomic-embed-text"), "input": texts}, timeout=120)
    response.raise_for_status(); return response.json()["embeddings"]
def ensure_vector_collection():
    client = _qdrant(); name = os.getenv("QDRANT_COLLECTION", "enterpriseai")
    try: client.get_collection(name)
    except Exception:
        dim = len(_embed(["dimension probe"])[0])
        client.create_collection(name, vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE))

def _chunks(text: str, size=1000, overlap=140):
    words = text.split(); result=[]; cursor=0
    while cursor < len(words):
        part = words[cursor:cursor+size]
        if part: result.append(" ".join(part))
        cursor += max(1, size-overlap)
    return result
def _graph_entities(text: str):
    return list(dict.fromkeys(re.findall(r"\b[A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,2}\b", text)))[:40]

def _falkor_graph():
    from falkordb import FalkorDB
    client = FalkorDB(host=os.getenv("FALKORDB_HOST", "falkordb"), port=int(os.getenv("FALKORDB_PORT", "6379")), password=os.getenv("FALKORDB_PASSWORD") or None)
    return client.select_graph(os.getenv("FALKORDB_GRAPH", "enterpriseai"))

def _persist_entity_graph(document_id: str, title: str, entities: list[str]):
    graph = _falkor_graph()
    graph.query("MERGE (d:Document {id:$id}) SET d.title=$title", {"id": document_id, "title": title})
    for entity in entities:
        graph.query("MERGE (e:Entity {name:$name})", {"name": entity})
        graph.query("MATCH (d:Document {id:$id}), (e:Entity {name:$name}) MERGE (d)-[:MENTIONS]->(e)", {"id": document_id, "name": entity})
    for left, right in zip(entities, entities[1:]):
        graph.query("MATCH (a:Entity {name:$left}), (b:Entity {name:$right}) MERGE (a)-[:CO_OCCURS_WITH]->(b)", {"left": left, "right": right})

def persist_run_entities(run_id: str, entities: list[str]):
    if not run_id or not entities:
        return {"stored": 0, "available": bool(run_id)}
    graph = _falkor_graph()
    graph.query("MERGE (i:Investigation {id:$id})", {"id": run_id})
    for entity in entities:
        graph.query("MERGE (e:Entity {name:$name})", {"name": entity})
        graph.query("MATCH (i:Investigation {id:$id}), (e:Entity {name:$name}) MERGE (i)-[:INVOLVES]->(e)", {"id": run_id, "name": entity})
    return {"stored": len(entities), "available": True}

def _graph_expand_sync(query: str, entities: list[str], limit: int = 10):
    names = entities or _graph_entities(query)
    if not names:
        return []
    try:
        graph = _falkor_graph()
        direct_rows = graph.query(
            "MATCH (e:Entity)<-[:MENTIONS]-(d:Document) "
            "WHERE e.name IN $names RETURN DISTINCT d.id, d.title, e.name LIMIT 30",
            {"names": names},
        ).result_set
        related_rows = graph.query(
            "MATCH (e:Entity)-[:CO_OCCURS_WITH]-(related:Entity)<-[:MENTIONS]-(d:Document) "
            "WHERE e.name IN $names RETURN DISTINCT d.id, d.title, related.name LIMIT 30",
            {"names": names},
        ).result_set
        rows = list(direct_rows) + list(related_rows)
    except Exception:
        return []
    results = []
    base = os.getenv("QDRANT_URL", "http://qdrant:6333").rstrip("/")
    collection = os.getenv("QDRANT_COLLECTION", "enterpriseai")
    for row in rows:
        if not row or not row[0]:
            continue
        try:
            response = requests.post(
                f"{base}/collections/{collection}/points/scroll",
                json={"filter": {"must": [{"key": "document_id", "match": {"value": str(row[0])}}]}, "limit": 4, "with_payload": True, "with_vectors": False},
                timeout=10,
            )
            response.raise_for_status()
            points = response.json().get("result", {}).get("points", [])
            for point in points:
                payload = point.get("payload", {})
                results.append({"document_id": str(row[0]), "title": payload.get("title") or row[1] or "Untitled", "text": payload.get("text", ""), "score": 0.18, "chunk_id": str(point.get("id", "")), "graph_entities": [str(row[2])] if len(row) > 2 else []})
        except Exception:
            continue
    unique = {}
    for item in results:
        unique[(item["document_id"], item["chunk_id"])] = item
    return list(unique.values())[:limit]

async def graph_expand(query: str, entities: list[str], limit: int = 10):
    return await asyncio.to_thread(_graph_expand_sync, query, entities, limit)
def index_text(title: str, media_type: str, text: str):
    document_id = str(uuid.uuid4()); parts = _chunks(text)
    if not parts: raise ValueError("No text could be extracted from the file")
    vectors = _embed(parts)
    client = _qdrant(); collection = os.getenv("QDRANT_COLLECTION", "enterpriseai")
    try: client.get_collection(collection)
    except Exception: client.create_collection(collection, vectors_config=models.VectorParams(size=len(vectors[0]), distance=models.Distance.COSINE))
    client.upsert(collection, points=[models.PointStruct(id=str(uuid.uuid4()), vector=vector, payload={"document_id":document_id,"title":title,"media_type":media_type,"chunk_index":i,"text":part}) for i,(part,vector) in enumerate(zip(parts,vectors))], wait=True)
    entities = _graph_entities(text)
    _persist_entity_graph(document_id, title, entities)
    with SessionLocal.begin() as db: db.add(KnowledgeDocument(id=document_id,title=title,media_type=media_type,chunk_count=len(parts)))
    return {"id":document_id,"title":title,"media_type":media_type,"chunk_count":len(parts),"entities":len(entities)}

def _hybrid_retrieve_sync(query: str, limit=6):
    cache=None
    try:
        from redis import Redis
        cache=Redis.from_url(os.getenv("REDIS_URL","redis://redis:6379/0"),decode_responses=True)
        cached=cache.get("retrieval:"+hashlib.sha256(query.encode()).hexdigest())
        if cached: return json.loads(cached)
    except Exception: cache=None
    try:
        vector=_embed([query])[0]
        response=requests.post(os.getenv("QDRANT_URL","http://qdrant:6333").rstrip("/")+f"/collections/{os.getenv('QDRANT_COLLECTION','enterpriseai')}/points/query",json={"query":vector,"limit":limit*3,"with_payload":True},timeout=30)
        response.raise_for_status(); points=response.json().get("result",{}).get("points",[])
    except Exception: points=[]
    terms=set(re.findall(r"\w+",query.lower())); hits=[]
    for point in points:
        payload=point.get("payload",{}); txt=payload.get("text",""); lexical=len(terms & set(re.findall(r"\w+",txt.lower())))/max(1,len(terms)); vector_score=float(point.get("score",0)); score=.72*vector_score+.28*lexical
        hits.append({"document_id":payload.get("document_id",""),"title":payload.get("title","Untitled"),"text":txt,"score":score})
    hits.sort(key=lambda h:h["score"],reverse=True)
    result=hits[:limit]
    if cache:
        try: cache.setex("retrieval:"+hashlib.sha256(query.encode()).hexdigest(),90,json.dumps(result))
        except Exception: pass
    return result

async def hybrid_retrieve(query: str, limit=6):
    return await asyncio.to_thread(_hybrid_retrieve_sync,query,limit)

async def publish_event(event: dict):
    from redis import Redis
    client = Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
    client.xadd(os.getenv("REDIS_STREAM", "enterpriseai:events"), {"payload": json.dumps(event, ensure_ascii=False), "attempts": "0"})
    client.close()

def extract_file(filename: str, content_type: str, data: bytes) -> str:
    suffix=filename.lower().rsplit(".",1)[-1] if "." in filename else ""
    if suffix=="pdf":
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
    if suffix=="docx":
        from docx import Document
        return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    if suffix in {"txt","md","csv","json","xml","html"} or content_type.startswith("text/"):
        return data.decode("utf-8",errors="ignore")
    if content_type.startswith("image/"):
        import base64
        response=requests.post(os.getenv("OLLAMA_BASE_URL","http://ollama:11434").rstrip("/")+"/api/generate",json={"model":os.getenv("VISION_MODEL","llava:7b"),"prompt":"Describe this image accurately and extract visible text.","images":[base64.b64encode(data).decode()],"stream":False},timeout=180)
        response.raise_for_status(); return response.json().get("response","")
    if content_type.startswith("audio/") or suffix in {"mp3","wav","m4a","ogg"}:
        from faster_whisper import WhisperModel
        path=f"/tmp/{uuid.uuid4()}.{suffix or 'audio'}"
        with open(path,"wb") as f: f.write(data)
        try:
            model=WhisperModel(os.getenv("WHISPER_MODEL","small"),device="cpu",compute_type="int8")
            segments,_=model.transcribe(path)
            return "\n".join(seg.text for seg in segments)
        finally: os.remove(path)
    if content_type.startswith("video/") or suffix in {"mp4","mov","mkv","webm"}:
        with tempfile.TemporaryDirectory() as folder:
            source=os.path.join(folder,"source."+(suffix or "mp4")); audio=os.path.join(folder,"audio.wav"); frame=os.path.join(folder,"frame-%02d.jpg")
            with open(source,"wb") as f: f.write(data)
            subprocess.run(["ffmpeg","-v","error","-i",source,"-vn","-ac","1","-ar","16000",audio],check=False,timeout=120)
            subprocess.run(["ffmpeg","-v","error","-i",source,"-vf","fps=1/30,scale=1024:-1","-frames:v","8",frame],check=False,timeout=120)
            transcripts=[]
            if os.path.exists(audio) and os.path.getsize(audio)>44:
                transcripts.append(extract_file("audio.wav","audio/wav",open(audio,"rb").read()))
            for frame_path in glob.glob(os.path.join(folder,"frame-*.jpg")):
                with open(frame_path,"rb") as f: transcripts.append(extract_file("frame.jpg","image/jpeg",f.read()))
            return "\n\n".join(transcripts)
    raise ValueError("Supported files: PDF, DOCX, TXT, MD, CSV, JSON, images, and audio. Video ingestion accepts MP4 and extracts audio/frames in the processing pipeline.")


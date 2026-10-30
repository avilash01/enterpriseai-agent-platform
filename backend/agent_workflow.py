"""Eight cooperating specialist agents orchestrated as a LangGraph state graph."""
from __future__ import annotations

import os
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

AGENT_NAMES = ["intake_planner", "research_analyst", "knowledge_retriever", "analysis_agent", "writing_agent", "quality_reviewer", "decision_agent", "automation_planner"]

class AgentState(TypedDict, total=False):
    request: str
    attachments: list[str]
    plan: str
    research: str
    retrieval: str
    analysis: str
    draft: str
    reviewed: str
    decision: str
    answer: str
    citations: list[dict]
    run_id: str

def _model():
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    model_name = os.getenv("LLM_MODEL", "qwen2.5:7b")
    if provider == "ollama":
        return ChatOllama(model=model_name, base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"), temperature=0.2)
    if provider == "groq":
        return ChatGroq(model=model_name, api_key=os.environ["GROQ_API_KEY"], temperature=0.2)
    raise RuntimeError("LLM_PROVIDER must be ollama or groq")

def build_workflow(retrieve):
    llm = _model()
    async def call(role: str, task: str, context: str) -> str:
        result = await llm.ainvoke([SystemMessage(content=f"You are the {role}. Be precise, grounded, and concise. Do not claim tools or actions that did not run. {task}"), HumanMessage(content=context)])
        return str(result.content)
    async def intake(s: AgentState):
        return {"plan": await call("Intake Planner", "Clarify the deliverable and make a bounded plan.", s["request"])}
    async def research(s: AgentState):
        return {"research": await call("Research Analyst", "Extract evidence from the user request and provided attachments. Separate known facts from unknowns.", f"Request: {s['request']}\nAttachments: {s.get('attachments', [])}\nPlan: {s.get('plan', '')}")}
    async def knowledge(s: AgentState):
        hits = await retrieve(s["request"])
        citations = [{"document_id": h["document_id"], "title": h["title"], "snippet": h["text"][:400], "score": h["score"]} for h in hits]
        evidence = "\n".join(f"[{i+1}] {h['title']}: {h['text']}" for i,h in enumerate(hits)) or "No indexed documents matched this request."
        note = await call("Knowledge Retriever", "Use retrieved passages. Explicitly say when no indexed source was found. Never invent citations.", f"Request: {s['request']}\nPassages:\n{evidence}")
        return {"retrieval": note, "citations": citations}
    async def analysis(s: AgentState):
        return {"analysis": await call("Analysis Agent", "Reason over supplied facts and retrieval. Mark inference and risks.", f"Request: {s['request']}\nResearch: {s['research']}\nKnowledge: {s['retrieval']}")}
    async def writing(s: AgentState):
        return {"draft": await call("Writing Agent", "Write a useful, structured first draft, retaining uncertainty and source markers.", f"Request: {s['request']}\nPlan: {s['plan']}\nEvidence: {s['research']}\nRetrieval: {s['retrieval']}\nAnalysis: {s['analysis']}")}
    async def review(s: AgentState):
        return {"reviewed": await call("Quality Reviewer", "Correct unsupported statements, answer the request, and keep source markers only for actual citations.", f"Draft: {s['draft']}\nAvailable citations: {s.get('citations', [])}")}
    async def decision(s: AgentState):
        return {"decision": await call("Decision Agent", "Provide a brief recommendation and say when human approval is needed. Do not execute tools.", f"Request: {s['request']}\nReviewed answer: {s['reviewed']}")}
    async def automation(s: AgentState):
        answer = await call("Automation Planner", "Return the reviewed answer. Do not claim external actions ran.", f"Reviewed answer: {s['reviewed']}\nDecision: {s['decision']}")
        return {"answer": answer}
    graph = StateGraph(AgentState)
    for name, node in zip(AGENT_NAMES, [intake,research,knowledge,analysis,writing,review,decision,automation]): graph.add_node(name, node)
    graph.add_edge(START, AGENT_NAMES[0])
    for current, following in zip(AGENT_NAMES, AGENT_NAMES[1:]): graph.add_edge(current, following)
    graph.add_edge(AGENT_NAMES[-1], END)
    return graph.compile()

async def evaluate_run(question: str, answer: str, citations: list[dict]):
    """LLM-as-judge rubric. Scores are review signals, not a guarantee of correctness."""
    import json, re
    result=await _model().ainvoke([
        SystemMessage(content="Evaluate the answer against the question and supplied citations. Return JSON only with scores groundedness, completeness, clarity as integers 1 through 5, and a short rationale. Do not reward unsupported assertions. A score is a review signal, not a truth guarantee."),
        HumanMessage(content=json.dumps({"question":question,"answer":answer,"citations":citations},ensure_ascii=False)),
    ])
    raw=str(result.content)
    match=re.search(r"\{.*\}",raw,re.S)
    if not match: raise RuntimeError("Evaluation model did not return the required JSON rubric")
    data=json.loads(match.group())
    for key in ("groundedness","completeness","clarity"):
        data[key]=max(1,min(5,int(data[key])))
    data["rationale"]=str(data.get("rationale",""))[:2000]
    data["disclaimer"]="Model-assisted rubric; human review is required for consequential decisions."
    return data

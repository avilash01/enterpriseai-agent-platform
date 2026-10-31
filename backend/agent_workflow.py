"""Thirty functional investigation agents orchestrated as a LangGraph state graph.

Agents with deterministic work do not call the model. Specialist synthesis agents
share an Ollama/Groq model client, keeping the local-first execution affordable.
"""
from __future__ import annotations

import json
import operator
import os
import re
from dataclasses import asdict, dataclass
from typing import Annotated, Any, Callable, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph


@dataclass(frozen=True)
class AgentDefinition:
    id: str
    name: str
    responsibility: str
    input_schema: str
    output_schema: str
    execution: str


AGENT_CATALOG = [
    AgentDefinition("master_investigation", "Master Investigation Agent", "Frame the investigation question, objective, and constraints.", "request, attachments", "investigation_scope", "llm"),
    AgentDefinition("planner", "Planner Agent", "Decompose the request into bounded investigation stages.", "request, investigation_scope", "plan", "rule"),
    AgentDefinition("task_router", "Task Router Agent", "Route the request across evidence, graph, timeline, and risk analysis.", "request, plan", "routes", "rule"),
    AgentDefinition("scope_validator", "Scope Validation Agent", "Validate that the investigation plan is specific and safe.", "request, plan", "scope_check", "rule"),
    AgentDefinition("source_discovery", "Source Discovery Agent", "Identify available user-provided and indexed evidence sources.", "request, attachments", "source_inventory", "rule"),
    AgentDefinition("attachment_parser", "Attachment Parsing Agent", "Normalize supplied attachment text for downstream processing.", "attachments", "attachment_text", "rule"),
    AgentDefinition("data_ingestion", "Data Ingestion Agent", "Prepare request and attachment material for evidence analysis.", "request, attachment_text", "ingested_material", "rule"),
    AgentDefinition("data_validation", "Data Validation Agent", "Check evidence inputs for emptiness, duplication, and malformed values.", "ingested_material", "validation", "rule"),
    AgentDefinition("entity_extractor", "Entity Extraction Agent", "Extract candidate named entities from the investigation context.", "request, ingested_material", "entities", "rule"),
    AgentDefinition("entity_resolution", "Entity Resolution Agent", "Normalize entity spelling and merge duplicate surface forms.", "entities", "resolved_entities", "rule"),
    AgentDefinition("vector_retriever", "Vector Retrieval Agent", "Retrieve semantically similar indexed passages from Qdrant.", "request", "vector_hits", "tool"),
    AgentDefinition("graph_builder", "Graph Builder Agent", "Persist investigation-to-entity and document-to-entity relationships in FalkorDB.", "run_id, resolved_entities", "graph_status", "tool"),
    AgentDefinition("graph_traversal", "Graph Traversal Agent", "Expand entities through related documents and graph neighbors.", "request, resolved_entities", "graph_hits", "tool"),
    AgentDefinition("lexical_retriever", "Lexical Retrieval Agent", "Score retrieved passages for exact term overlap.", "request, vector_hits, graph_hits", "lexical_hits", "rule"),
    AgentDefinition("hybrid_ranker", "Hybrid Ranking Agent", "Merge semantic, lexical, and graph evidence with reciprocal rank fusion.", "vector_hits, graph_hits, lexical_hits", "ranked_hits", "rule"),
    AgentDefinition("evidence_extractor", "Evidence Extraction Agent", "Extract claims and source passages relevant to the question.", "request, ranked_hits", "evidence", "rule"),
    AgentDefinition("evidence_validator", "Evidence Validation Agent", "Check evidence provenance and required fields before synthesis.", "evidence, ranked_hits", "evidence_check", "rule"),
    AgentDefinition("counter_evidence", "Counter-Evidence Agent", "Flag passages that may contradict or qualify the leading evidence.", "request, ranked_hits", "counter_evidence", "rule"),
    AgentDefinition("timeline_builder", "Timeline Agent", "Extract date-bearing evidence into a chronologically ordered timeline.", "ranked_hits", "timeline", "rule"),
    AgentDefinition("relationship_analyst", "Relationship Analysis Agent", "Interpret graph-expanded relationships and their source support.", "request, graph_hits, evidence", "relationship_analysis", "llm"),
    AgentDefinition("hypothesis_generator", "Hypothesis Agent", "Generate bounded hypotheses and label them as inference.", "request, evidence, relationship_analysis, counter_evidence", "hypotheses", "llm"),
    AgentDefinition("confidence_scorer", "Evidence Confidence Agent", "Estimate retrieval confidence from rank, support, and provenance signals.", "ranked_hits, evidence_check", "confidence", "rule"),
    AgentDefinition("risk_assessor", "Risk Assessment Agent", "Identify uncertainty, sensitivity, and consequential-decision risks.", "request, evidence, hypotheses", "risk_assessment", "llm"),
    AgentDefinition("fact_checker", "Fact Verification Agent", "Review claims against only the supplied evidence and mark gaps.", "request, evidence, hypotheses", "fact_check", "llm"),
    AgentDefinition("bias_reviewer", "Bias Review Agent", "Flag one-sided evidence and unsupported assumptions.", "request, evidence, counter_evidence", "bias_review", "rule"),
    AgentDefinition("report_outliner", "Report Outline Agent", "Build a response outline that preserves sources and uncertainty.", "request, evidence, timeline, risk_assessment", "report_outline", "rule"),
    AgentDefinition("report_writer", "Report Generation Agent", "Write the investigation report with evidence and caveats.", "request, plan, evidence, hypotheses, timeline, report_outline", "draft", "llm"),
    AgentDefinition("citation_auditor", "Citation Audit Agent", "Remove citations that do not map to retrieved documents.", "draft, citations", "citation_audit", "rule"),
    AgentDefinition("quality_reviewer", "Quality Review Agent", "Review answer completeness, clarity, grounding, and safety.", "request, draft, evidence, citation_audit", "reviewed_report", "llm"),
    AgentDefinition("automation_planner", "Decision and Automation Planning Agent", "Summarize evidence-supported next steps and prepare a proposal for human-approved workflow actions.", "request, reviewed_report, confidence, risk_assessment", "decision, answer, automation_plan", "rule"),
]

AGENT_NAMES = [agent.id for agent in AGENT_CATALOG]


class AgentState(TypedDict, total=False):
    request: str
    attachments: list[str]
    run_id: str
    investigation_scope: str
    plan: list[str]
    routes: list[str]
    scope_check: dict[str, Any]
    source_inventory: list[str]
    attachment_text: str
    ingested_material: str
    validation: dict[str, Any]
    entities: list[str]
    resolved_entities: list[str]
    vector_hits: list[dict[str, Any]]
    graph_status: dict[str, Any]
    graph_hits: list[dict[str, Any]]
    lexical_hits: list[dict[str, Any]]
    ranked_hits: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    evidence_check: dict[str, Any]
    counter_evidence: list[dict[str, Any]]
    timeline: list[dict[str, str]]
    relationship_analysis: str
    hypotheses: str
    confidence: dict[str, Any]
    risk_assessment: str
    fact_check: str
    bias_review: list[str]
    report_outline: list[str]
    draft: str
    citations: list[dict[str, Any]]
    citation_audit: dict[str, Any]
    reviewed_report: str
    decision: str
    automation_plan: dict[str, Any]
    answer: str
    agent_trace: Annotated[list[str], operator.add]


def _model():
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    model_name = os.getenv("LLM_MODEL", "qwen2.5:7b")
    if provider == "ollama":
        return ChatOllama(model=model_name, base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"), temperature=0.2)
    if provider == "groq":
        key = os.getenv("GROQ_API_KEY", "")
        if not key:
            raise RuntimeError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        return ChatGroq(model=model_name, api_key=key, temperature=0.2)
    raise RuntimeError("LLM_PROVIDER must be ollama or groq")


async def _ask(llm, role: str, instructions: str, context: Any) -> str:
    result = await llm.ainvoke([
        SystemMessage(content=f"You are the {role}. Be concise, evidence-grounded, and explicit about uncertainty. Never claim actions that did not run. {instructions}"),
        HumanMessage(content=json.dumps(context, ensure_ascii=False, default=str)),
    ])
    return str(result.content)


def build_workflow(retrieve, graph_expand=None, persist_entities=None):
    """Build a 30-node workflow; rule agents are deterministic, specialists use the LLM."""
    llm = _model()

    async def master(s):
        scope = await _ask(llm, "Master Investigation Agent", "State the objective, scope, and missing information.", {"request": s["request"], "attachments": s.get("attachments", [])})
        return {"investigation_scope": scope}

    async def planner(s):
        return {"plan": ["Validate the request and available material", "Retrieve and rank vector and graph evidence", "Analyze evidence, contradictions, timeline, and risk", "Draft and verify a cited response", "Prepare actions for explicit approval only"]}

    async def router(s):
        text = s["request"].lower()
        routes = ["evidence", "graph"]
        if re.search(r"when|timeline|history|sequence|date", text): routes.append("timeline")
        if re.search(r"risk|safe|impact|should|recommend", text): routes.append("risk")
        return {"routes": routes}

    async def scope_validator(s):
        return {"scope_check": {"valid": bool(s["request"].strip()), "characters": len(s["request"]), "within_limit": len(s["request"]) <= 12000}}

    async def source_discovery(s):
        sources = (["user_attachments"] if s.get("attachments") else []) + ["qdrant_vector_index", "falkordb_knowledge_graph"]
        return {"source_inventory": sources}

    async def attachment_parser(s):
        return {"attachment_text": "\n\n".join(str(x)[:20000] for x in s.get("attachments", []))}

    async def ingestion(s):
        return {"ingested_material": (s["request"] + "\n" + s.get("attachment_text", ""))[:50000]}

    async def validation(s):
        material = s.get("ingested_material", "")
        return {"validation": {"non_empty": bool(material.strip()), "characters": len(material), "duplicate_lines_removed": len(material.splitlines()) - len(set(material.splitlines()))}}

    async def extract_entities(s):
        pattern = r"\b[A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,2}\b"
        return {"entities": list(dict.fromkeys(re.findall(pattern, s.get("ingested_material", ""))))[:80]}

    async def resolve_entities(s):
        entities = {}
        for item in s.get("entities", []):
            canonical = " ".join(item.strip().split())
            entities.setdefault(canonical.casefold(), canonical)
        return {"resolved_entities": list(entities.values())}

    async def vector_retriever(s):
        hits = await retrieve(s["request"])
        return {"vector_hits": hits}

    async def graph_builder(s):
        if persist_entities:
            result = await persist_entities(s.get("run_id", ""), s.get("resolved_entities", []))
        else:
            result = {"stored": 0, "available": False}
        return {"graph_status": result}

    async def graph_traversal(s):
        hits = await graph_expand(s["request"], s.get("resolved_entities", [])) if graph_expand else []
        return {"graph_hits": hits}

    async def lexical_retriever(s):
        terms = set(re.findall(r"\w+", s["request"].casefold()))
        hits = []
        for hit in s.get("vector_hits", []):
            text = str(hit.get("text", ""))
            overlap = len(terms & set(re.findall(r"\w+", text.casefold()))) / max(1, len(terms))
            hits.append({**hit, "lexical_score": overlap})
        return {"lexical_hits": hits}

    async def hybrid_ranker(s):
        fused = {}
        for channel, items in (("vector", s.get("vector_hits", [])), ("graph", s.get("graph_hits", [])), ("lexical", s.get("lexical_hits", []))):
            for rank, hit in enumerate(items, 1):
                key = (hit.get("document_id", ""), hit.get("chunk_id", hit.get("text", "")))
                target = fused.setdefault(key, {**hit, "score": 0.0, "channels": []})
                target["score"] += 1 / (60 + rank)
                target["channels"].append(channel)
                if channel == "vector": target["score"] += 0.35 * float(hit.get("score", 0))
                if channel == "lexical": target["score"] += 0.25 * float(hit.get("lexical_score", 0))
        ranked = sorted(fused.values(), key=lambda row: row["score"], reverse=True)[:12]
        citations = [{"document_id": h.get("document_id", ""), "title": h.get("title", "Untitled"), "snippet": str(h.get("text", ""))[:400], "score": float(h["score"]), "channels": h["channels"]} for h in ranked if h.get("document_id")]
        return {"ranked_hits": ranked, "citations": citations}

    async def evidence_extractor(s):
        return {"evidence": [{"claim": h.get("text", ""), "source": h.get("title", "Untitled"), "document_id": h.get("document_id", ""), "score": h.get("score", 0.0)} for h in s.get("ranked_hits", [])]}

    async def evidence_validator(s):
        evidence = s.get("evidence", [])
        valid = [e for e in evidence if e.get("document_id") and e.get("claim")]
        return {"evidence_check": {"valid_count": len(valid), "invalid_count": len(evidence) - len(valid), "has_retrieved_sources": bool(valid)}}

    async def counter_evidence(s):
        cues = ("however", "although", "contrary", "not", "no evidence", "dispute", "failed", "declined", "risk", "exception")
        request_terms = set(re.findall(r"\w+", s["request"].casefold()))
        rows = []
        for hit in s.get("ranked_hits", []):
            text = str(hit.get("text", ""))
            if any(cue in text.casefold() for cue in cues) and request_terms & set(re.findall(r"\w+", text.casefold())):
                rows.append({"title": hit.get("title", "Untitled"), "text": text[:500], "document_id": hit.get("document_id", "")})
        return {"counter_evidence": rows[:5]}

    async def timeline(s):
        rows = []
        for hit in s.get("ranked_hits", []):
            text = str(hit.get("text", ""))
            for match in re.finditer(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})\b", text, re.I):
                rows.append({"date": match.group(), "source": hit.get("title", "Untitled"), "context": text[max(0, match.start()-100):match.end()+150]})
        return {"timeline": rows[:30]}

    async def relationships(s):
        return {"relationship_analysis": await _ask(llm, "Relationship Analysis Agent", "Describe only graph relationships supported by the returned passages. State when graph support is absent.", {"request": s["request"], "graph_hits": s.get("graph_hits", []), "evidence": s.get("evidence", [])})}

    async def hypotheses(s):
        return {"hypotheses": await _ask(llm, "Hypothesis Agent", "Offer up to three clearly labeled hypotheses; distinguish inference from verified evidence.", {"request": s["request"], "evidence": s.get("evidence", []), "relationships": s.get("relationship_analysis", ""), "counter_evidence": s.get("counter_evidence", [])})}

    async def confidence(s):
        hits = s.get("ranked_hits", [])
        top = float(hits[0].get("score", 0)) if hits else 0
        count = len(s.get("evidence", []))
        return {"confidence": {"level": "low" if not count or top < .02 else "moderate" if count < 3 or top < .08 else "strong", "supporting_sources": count, "top_rank_score": round(top, 4), "method": "retrieval rank and source count heuristic"}}

    async def risks(s):
        return {"risk_assessment": await _ask(llm, "Risk Assessment Agent", "List uncertainty and possible decision risks. Do not provide professional legal, medical, or financial determinations.", {"request": s["request"], "evidence": s.get("evidence", []), "hypotheses": s.get("hypotheses", "")})}

    async def fact_check(s):
        return {"fact_check": await _ask(llm, "Fact Verification Agent", "Classify important conclusions as supported, contradicted, or unknown using only evidence below.", {"request": s["request"], "evidence": s.get("evidence", []), "hypotheses": s.get("hypotheses", "")})}

    async def bias(s):
        notes = []
        if not s.get("counter_evidence"): notes.append("No counter-evidence cue was detected by the lexical scan; absence is not proof of no counter-evidence.")
        if len(s.get("evidence", [])) < 2: notes.append("Evidence base is narrow; seek independent sources before relying on conclusions.")
        if not notes: notes.append("Review both supporting and qualifying passages; automated lexical screening may miss subtle bias.")
        return {"bias_review": notes}

    async def outline(s):
        return {"report_outline": ["Executive finding", "Evidence and source support", "Relationships and timeline", "Counter-evidence and uncertainty", "Risks and recommended next steps"]}

    async def writer(s):
        return {"draft": await _ask(llm, "Report Generation Agent", "Write a structured investigation report using the supplied evidence IDs for citations. Never invent sources; say when the index has no relevant sources.", {"request": s["request"], "plan": s.get("plan"), "evidence": s.get("evidence", []), "hypotheses": s.get("hypotheses", ""), "timeline": s.get("timeline", []), "outline": s.get("report_outline", [])})}

    async def citation_audit(s):
        ids = {str(c.get("document_id")) for c in s.get("citations", []) if c.get("document_id")}
        draft = s.get("draft", "")
        cited = re.findall(r"\[([0-9a-f-]{20,})\]", draft, re.I)
        invalid = [c for c in cited if c not in ids]
        return {"citation_audit": {"known_document_ids": sorted(ids), "unverified_ids": invalid, "citations_present": len(cited)}}

    async def reviewer(s):
        return {"reviewed_report": await _ask(llm, "Quality Review Agent", "Correct unsupported specificity, retain uncertainty, do not add source claims, and produce the final response.", {"request": s["request"], "draft": s.get("draft", ""), "evidence": s.get("evidence", []), "citation_audit": s.get("citation_audit", {})})}

    async def automation(s):
        final = s.get("reviewed_report") or s.get("draft") or "No report was generated."
        confidence = s.get("confidence", {}).get("level", "low")
        risk = s.get("risk_assessment", "")
        decision_text = f"Evidence confidence: {confidence}. Human review is recommended before consequential action. Risk notes: {risk[:700]}"
        return {"decision": decision_text, "answer": final, "automation_plan": {"requires_human_approval": True, "proposed_event": "enterpriseai.run.completed", "request_and_answer_forwarded_only_after_approval": True}}

    nodes: dict[str, Callable] = {
        "master_investigation": master, "planner": planner, "task_router": router, "scope_validator": scope_validator,
        "source_discovery": source_discovery, "attachment_parser": attachment_parser, "data_ingestion": ingestion,
        "data_validation": validation, "entity_extractor": extract_entities, "entity_resolution": resolve_entities,
        "vector_retriever": vector_retriever, "graph_builder": graph_builder, "graph_traversal": graph_traversal,
        "lexical_retriever": lexical_retriever, "hybrid_ranker": hybrid_ranker, "evidence_extractor": evidence_extractor,
        "evidence_validator": evidence_validator, "counter_evidence": counter_evidence, "timeline_builder": timeline,
        "relationship_analyst": relationships, "hypothesis_generator": hypotheses, "confidence_scorer": confidence,
        "risk_assessor": risks, "fact_checker": fact_check, "bias_reviewer": bias, "report_outliner": outline,
        "report_writer": writer, "citation_auditor": citation_audit, "quality_reviewer": reviewer,
        "automation_planner": automation,
    }

    graph = StateGraph(AgentState)
    for definition in AGENT_CATALOG:
        node = nodes[definition.id]
        async def traced(state, agent_id=definition.id, execute=node):
            update = await execute(state)
            return {**update, "agent_trace": [agent_id]}
        graph.add_node(definition.id, traced)
    graph.add_edge(START, AGENT_NAMES[0])
    for current, following in zip(AGENT_NAMES, AGENT_NAMES[1:]):
        graph.add_edge(current, following)
    graph.add_edge(AGENT_NAMES[-1], END)
    return graph.compile()


async def evaluate_run(question: str, answer: str, citations: list[dict]):
    """LLM-as-judge rubric. Scores are review signals, not a guarantee of correctness."""
    result = await _model().ainvoke([
        SystemMessage(content="Evaluate the answer against the question and supplied citations. Return JSON only with scores groundedness, completeness, clarity as integers 1 through 5, and a short rationale. Do not reward unsupported assertions. A score is a review signal, not a truth guarantee."),
        HumanMessage(content=json.dumps({"question": question, "answer": answer, "citations": citations}, ensure_ascii=False)),
    ])
    match = re.search(r"\{.*\}", str(result.content), re.S)
    if not match: raise RuntimeError("Evaluation model did not return the required JSON rubric")
    data = json.loads(match.group())
    for key in ("groundedness", "completeness", "clarity"):
        data[key] = max(1, min(5, int(data[key])))
    data["rationale"] = str(data.get("rationale", ""))[:2000]
    data["disclaimer"] = "Model-assisted rubric; human review is required for consequential decisions."
    return data


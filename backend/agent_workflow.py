"""Eight-specialist EnterpriseAI pipeline implemented with Google's ADK."""
import os

from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.models.lite_llm import LiteLlm

AGENT_NAMES = [
    "intake_planner",
    "research_analyst",
    "knowledge_retriever",
    "analysis_agent",
    "writing_agent",
    "quality_reviewer",
    "decision_agent",
    "automation_planner",
]


def _model():
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    model_name = os.getenv("LLM_MODEL", "llama3.2")
    if provider == "groq":
        if not os.getenv("GROQ_API_KEY"):
            raise RuntimeError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        return LiteLlm(model=f"groq/{model_name}")
    if provider == "ollama":
        os.environ.setdefault("OLLAMA_API_BASE", os.getenv("OLLAMA_API_BASE", "http://host.docker.internal:11434"))
        return LiteLlm(model=f"ollama_chat/{model_name}")
    raise RuntimeError("LLM_PROVIDER must be 'ollama' or 'groq'")


def build_workflow():
    model = _model()
    intake = LlmAgent(
        name=AGENT_NAMES[0],
        model=model,
        description="Clarifies the request and proposes a bounded plan.",
        instruction="""You are the Intake Planner. Restate the user's objective in one line, identify the requested deliverable, and create a short ordered plan. Do not perform external actions or invent missing context.""",
        output_key="work_plan",
    )
    research = LlmAgent(
        name=AGENT_NAMES[1],
        model=model,
        description="Extracts useful evidence from the request and supplied context.",
        instruction="""You are the Research Analyst. Work only from the user's request and context actually present. Do not claim web, file, or knowledge-base searches. Identify relevant supplied facts, assumptions, and unknowns.

Plan:
{work_plan}""",
        output_key="research_notes",
    )
    retrieval = LlmAgent(
        name=AGENT_NAMES[2],
        model=model,
        description="Checks for available retrieval context and reports coverage honestly.",
        instruction="""You are the Knowledge Retriever. No vector or graph retrieval tool is currently connected. Do not fabricate retrieved passages or sources. Summarize any source material explicitly supplied in the conversation; otherwise state that no indexed knowledge sources were available for this run.

Research notes:
{research_notes}""",
        output_key="retrieval_notes",
    )
    analysis = LlmAgent(
        name=AGENT_NAMES[3],
        model=model,
        description="Separates evidence from inference and analyzes the task.",
        instruction="""You are the Analysis Agent. Analyze the request using the research notes and retrieval coverage. Separate supported facts from inference, surface material risks, and create a concise answer plan. Never treat missing retrieval as evidence.

Research:
{research_notes}

Retrieval:
{retrieval_notes}""",
        output_key="analysis_notes",
    )
    writing = LlmAgent(
        name=AGENT_NAMES[4],
        model=model,
        description="Drafts a useful response grounded in the workflow state.",
        instruction="""You are the Writing Agent. Draft a direct, useful response to the user's request using the plan, research, retrieval status, and analysis. Preserve uncertainty and do not invent citations or claim actions that were not performed.

Plan: {work_plan}
Research: {research_notes}
Retrieval: {retrieval_notes}
Analysis: {analysis_notes}""",
        output_key="draft_answer",
    )
    review = LlmAgent(
        name=AGENT_NAMES[5],
        model=model,
        description="Reviews grounding, completeness, and clarity.",
        instruction="""You are the Quality Reviewer. Check the draft for unsupported claims, missing caveats, and clarity. Return a corrected draft only. Do not imply company documents were searched when retrieval reported none.

Draft:
{draft_answer}

Retrieval status:
{retrieval_notes}""",
        output_key="reviewed_answer",
    )
    decision = LlmAgent(
        name=AGENT_NAMES[6],
        model=model,
        description="Makes a recommendation without executing external actions.",
        instruction="""You are the Decision Agent. Review the user's objective and the reviewed answer. State the best next step or recommendation, and whether a human should review it. You cannot approve or execute external actions. Keep this as a short internal note for the final agent.

Reviewed answer:
{reviewed_answer}""",
        output_key="decision_note",
    )
    automation = LlmAgent(
        name=AGENT_NAMES[7],
        model=model,
        description="Prepares the final response and a safe, optional Zapier follow-up.",
        instruction="""You are the Automation Planner and final response agent. Return the reviewed answer to the user. If useful, append one concise suggested Zapier follow-up, clearly labeled as a suggestion. Never claim a Zap action ran. Zapier receives only a run-completed metadata event after explicit user approval; this agent cannot send prompts or answers to Zapier.

Reviewed answer:
{reviewed_answer}

Decision note:
{decision_note}""",
        output_key="final_answer",
    )
    return SequentialAgent(
        name="enterpriseai_orchestrator",
        description="Runs eight specialist agents in a traceable deterministic sequence.",
        sub_agents=[intake, research, retrieval, analysis, writing, review, decision, automation],
    )

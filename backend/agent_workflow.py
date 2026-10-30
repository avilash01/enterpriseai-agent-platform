"""EnterpriseAI multi-agent pipeline implemented with Google's ADK."""
import os

from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.models.lite_llm import LiteLlm


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
    research = LlmAgent(
        name="research_agent",
        model=model,
        description="Frames the task and identifies evidence and missing information.",
        instruction="""You are the Research Analyst in a multi-agent workflow. Work only from the user's request and context actually present in this session. Do not claim to search the web, files, or a knowledge base unless a retrieval tool has provided results. Identify the key question, useful facts supplied by the user, assumptions, and unknowns. Be concise.""",
        output_key="research_notes",
    )
    analysis = LlmAgent(
        name="analysis_agent",
        model=model,
        description="Analyzes the research notes and builds a reasoned answer plan.",
        instruction="""You are the Analysis Agent. Analyze the request and the Research Analyst notes below. Separate supported facts from inference, surface risks, and create a short answer plan. Do not invent evidence.

Research notes:
{research_notes}""",
        output_key="analysis_notes",
    )
    writing = LlmAgent(
        name="writing_agent",
        model=model,
        description="Drafts a clear answer grounded in the preceding agent outputs.",
        instruction="""You are the Writing Agent. Draft a useful, direct response to the user's request using the research and analysis below. Preserve uncertainty, do not invent citations or claim actions that were not performed.

Research notes:
{research_notes}

Analysis:
{analysis_notes}""",
        output_key="draft_answer",
    )
    review = LlmAgent(
        name="quality_reviewer",
        model=model,
        description="Checks grounding, completeness, and clarity before returning the final answer.",
        instruction="""You are the Quality Reviewer. Check the draft for unsupported claims, missing caveats, and clarity. Return only the corrected final answer. If no retrieval results were supplied, do not imply the answer is grounded in company documents.

Draft:
{draft_answer}""",
        output_key="final_answer",
    )
    return SequentialAgent(
        name="enterpriseai_orchestrator",
        description="Runs research, analysis, writing, and quality review in sequence.",
        sub_agents=[research, analysis, writing, review],
    )

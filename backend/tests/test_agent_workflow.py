import asyncio

import agent_workflow


class FakeResponse:
    content = "A concise mock analysis grounded in the supplied passages."


class FakeLLM:
    async def ainvoke(self, messages):
        return FakeResponse()


def test_catalog_has_thirty_unique_contracts():
    catalog = agent_workflow.AGENT_CATALOG
    assert len(catalog) == 30
    assert len({agent.id for agent in catalog}) == 30
    assert all(agent.responsibility and agent.input_schema and agent.output_schema and agent.execution for agent in catalog)


def test_complete_graph_runs_all_agents_and_hybrid_retrieval(monkeypatch):
    monkeypatch.setattr(agent_workflow, "_model", FakeLLM)

    async def retrieve(_query):
        return [{"document_id": "doc-1", "chunk_id": "chunk-1", "title": "Project Atlas", "text": "Project Atlas launched on 2025-01-15. However, the launch was delayed.", "score": 0.91}]

    async def graph_expand(_query, _entities):
        return [{"document_id": "doc-1", "chunk_id": "chunk-1", "title": "Project Atlas", "text": "Project Atlas launched on 2025-01-15. However, the launch was delayed.", "score": 0.4}]

    async def persist_entities(_run_id, entities):
        return {"stored": len(entities), "available": True}

    workflow = agent_workflow.build_workflow(retrieve, graph_expand, persist_entities)
    result = asyncio.run(workflow.ainvoke({
        "request": "Summarize Project Atlas launch timeline and risks",
        "attachments": [],
        "run_id": "test-run",
    }))

    assert result["agent_trace"] == agent_workflow.AGENT_NAMES
    assert len(result["agent_trace"]) == 30
    assert result["answer"]
    assert result["citations"]
    assert result["timeline"][0]["date"] == "2025-01-15"
    assert result["counter_evidence"]
    assert result["decision"]
    assert result["automation_plan"]["requires_human_approval"] is True


"""Step 6: function calling, ToolNode, tools_condition, assistant route."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.assistant import _mock_agent, assistant_tools
from app.graph import build_graph
from app.nodes import rule_based_route, route_after_router


def test_router_mengenali_pertanyaan_data():
    assert rule_based_route("What is Sari's remaining budget?").route == "assistant"
    assert rule_based_route("Apa status CLM-003?").route == "assistant"
    assert rule_based_route("Process claim CLM-003").route == "claim"
    assert rule_based_route("What is the hotel expense limit per night?").route == "policy"
    assert route_after_router({"route": "assistant"}) == "assistant"


def test_tool_punya_nama_deskripsi_dan_argumen():
    t = {t.name: t for t in assistant_tools()}
    assert {"employee_profile", "claim_details"} <= set(t)
    assert "remaining budget" in t["employee_profile"].description
    assert "name" in t["employee_profile"].args


def test_mock_meminta_tool_lalu_menjawab():
    name = {t.name for t in assistant_tools()}
    msgs = [HumanMessage(content="What is Sari's remaining budget?")]
    ai = _mock_agent(msgs, name)
    assert [tc["name"] for tc in ai.tool_calls] == ["employee_profile"]
    assert ai.tool_calls[0]["args"] == {"name": "Sari"}
    msgs += [ai, ToolMessage(content="Sari remaining Rp3.000.000", tool_call_id=ai.tool_calls[0]["id"])]
    end = _mock_agent(msgs, name)
    assert not end.tool_calls and "Rp3.000.000" in end.content


def test_loop_agent_di_graph():
    s = build_graph().invoke({"request": "What is Sari's remaining budget and who is Sari's manager?"})
    assert s["route"] == "assistant" and s["final_status"] == "answered"
    assert "Rp3.000.000" in s["answer"] and "Tono" in s["answer"]
    kind = [type(m).__name__ for m in s["messages"]]
    assert kind == ["HumanMessage", "AIMessage", "ToolMessage", "AIMessage"]


def test_beberapa_tool_sekaligus():
    s = build_graph().invoke({"request": "What are the details of CLM-003, and what is Budi's remaining budget?"})
    called = [tc["name"] for m in s["messages"] if isinstance(m, AIMessage) for tc in m.tool_calls]
    assert sorted(called) == ["claim_details", "employee_profile"]
    assert "CLM-003" in s["answer"] and "Rp6.000.000" in s["answer"]


def test_jalur_klaim_tetap_workflow():
    s = build_graph().invoke({"request": "Process claim CLM-002"})
    assert s["route"] == "claim" and not s.get("messages")      # the claim path does not use the LLM agent

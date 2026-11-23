"""Helper functions for tests (not tests)."""


def task_per_superstep(graph, graph_input, config=None) -> dict[int, list[str]]:
    """{superstep number: [names of the nodes that ran]} from stream_mode='debug'."""
    result: dict[int, list[str]] = {}
    for ev in graph.stream(graph_input, config or {"configurable": {"thread_id": "x"}}, stream_mode="debug"):
        if ev["type"] == "task":
            result.setdefault(ev["step"], []).append(ev["payload"]["name"])
    return result


def superstep_dari(step: dict[int, list[str]], node: str) -> int:
    return next(s for s, name in step.items() if node in name)

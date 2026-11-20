"""Fungsi bantu untuk test (bukan test)."""


def task_per_superstep(graph, masukan, config=None) -> dict[int, list[str]]:
    """{nomor superstep: [nama node yang jalan]} dari stream_mode='debug'."""
    hasil: dict[int, list[str]] = {}
    for ev in graph.stream(masukan, config or {"configurable": {"thread_id": "x"}}, stream_mode="debug"):
        if ev["type"] == "task":
            hasil.setdefault(ev["step"], []).append(ev["payload"]["name"])
    return hasil


def superstep_dari(langkah: dict[int, list[str]], node: str) -> int:
    return next(s for s, nama in langkah.items() if node in nama)

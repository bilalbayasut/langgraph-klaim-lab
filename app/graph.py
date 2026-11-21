from __future__ import annotations
from langgraph.graph import END, START, StateGraph

from app.nodes import router
from app.state import KlaimState

def build_graph(checkpointer=None):
    """Rakit lalu compile graph.

    checkpointer baru kita bahas di Langkah 13 (app.py dan test akan memasangnya),
    jadi parameternya disiapkan dari sekarang.
    """
    g = StateGraph(KlaimState)          # 1. graph dengan bentuk state KlaimState
    g.add_node("router", router)         # 2. node bernama "router" menjalankan fungsi router
    g.add_edge(START, "router")          # 3. mulai dari router
    g.add_edge("router", END)            #    setelah router, selesai
    return g.compile(checkpointer=checkpointer)

graph = build_graph()
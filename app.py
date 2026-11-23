"""Run the claim graph from the terminal and see what happens in each superstep.

    uv run app.py "Process claim CLM-002"     # one request
    uv run app.py --chat                     # interactive mode: type requests repeatedly
    uv run app.py --draw
"""

from __future__ import annotations

import argparse
import json
import sys

from app.graph import build_graph


def brief(value, max_len: int = 100) -> str:
    """Any value -> one-line JSON text, truncated if too long."""
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def run(graph, graph_input, config=None) -> None:
    """Run the graph and print what each node writes, per superstep.

    stream_mode="debug" sends an event every time a node starts ("task") and finishes ("task_result").
    Every event carries the superstep number in event["step"].
    """
    for event in graph.stream(graph_input, config, stream_mode="debug"):
        if event["type"] != "task_result":           # only show nodes that have FINISHED
            continue
        node = event["payload"]                       # {"name": ..., "result": {...}, ...}
        print(f"superstep {event['step']}: {node['name']}")
        for field, value in (node["result"] or {}).items():
            print(f"    {field} = {brief(value)}")


def ask(prompt: str) -> str:
    """input(), but Ctrl+D / Ctrl+C count as done (empty string)."""
    try:
        text = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    if not sys.stdin.isatty():         # input from a pipe/file: echo it back so the output is easy to read
        print(text)
    return text


def chat(graph) -> None:
    """Interactive mode: type a request, Enter, see its supersteps, repeat. Empty Enter = quit."""
    print("Chat mode. Type a request and press Enter. Empty Enter or Ctrl+D to quit.")
    while text := ask("\nyou> "):
        run(graph, {"request": text})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the claim graph.")
    parser.add_argument("request", nargs="?", help='e.g.: "Process claim CLM-002"')
    parser.add_argument("--draw", action="store_true", help="draw the graph, then exit")
    parser.add_argument("--chat", action="store_true", help="interactive mode: type requests repeatedly")
    args = parser.parse_args()

    graph = build_graph()
    if args.draw:
        print(graph.get_graph().draw_ascii())
        return
    if args.chat:
        chat(graph)
        return
    if not args.request:
        parser.error('request text, e.g.: uv run app.py "Process claim CLM-002"')
    run(graph, {"request": args.request})


if __name__ == "__main__":
    main()

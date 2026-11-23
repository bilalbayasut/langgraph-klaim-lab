"""Rebuild _solutions/ from the code blocks in LAB.md (a lab maintenance tool, not part of the exercises).

LAB.md is the single source of the code. Every code block preceded by a comment
    <!-- code: app/nodes.py | add -->    (add new functions / replace functions with the same name)
    <!-- code: app/graph.py | full -->   (whole file content)
    <!-- remove: app/nodes.py | function_name -->
is applied in order. The result after every step is stored in _solutions/step-NN/.

  uv run scripts/build_solutions.py              build _solutions/
  uv run scripts/build_solutions.py --test       + test: the solution of step N must pass the tests of steps 1..N
  uv run scripts/build_solutions.py --output     + fill the <!-- output: N | command --> blocks in LAB.md

Commands in output blocks run from the folder _solutions/step-NN/, so `uv run app.py ...`
uses the app/ of that step's solution.
"""

from __future__ import annotations

import ast
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "LAB.md"
SOLUTIONS = ROOT / "_solutions"

RE_STEP = re.compile(r"^## Langkah (\d+)\b")
RE_CODE = re.compile(r"^<!-- code: (\S+) \| (full|add) -->\s*$")
RE_REMOVE = re.compile(r"^<!-- remove: (\S+) \| (.+?) -->\s*$")
RE_OUTPUT = re.compile(r"^<!-- output: (\d+) \| (.+?)(?: \| (\d+))? -->\s*$")


# ----------------------------------------------------------------------------- read LAB.md
def read_operations(text: str) -> list[tuple[int, str, str, str]]:
    ops, step = [], 0
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        b = lines[i]
        if m := RE_STEP.match(b):
            step = int(m.group(1))
        elif m := RE_REMOVE.match(b.strip()):
            ops.append((step, "remove", m.group(1), m.group(2)))
        elif m := RE_CODE.match(b.strip()):
            j = i + 1
            while not lines[j].strip():
                j += 1
            fence = lines[j]
            if not fence.lstrip().startswith("```"):
                raise SystemExit(f"LAB.md line {i + 1}: a code comment must be followed by a ``` block")
            indent = len(fence) - len(fence.lstrip())
            body, j = [], j + 1
            while lines[j].strip() != "```":
                body.append(lines[j][indent:])
                j += 1
            ops.append((step, m.group(2), m.group(1), "\n".join(body) + "\n"))
            i = j
        i += 1
    return ops


# ----------------------------------------------------------------------------- code operations
def _name(node: ast.stmt) -> str | None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    if isinstance(node, ast.If) and "__main__" in ast.unparse(node.test):
        return "__main__"
    return None


def _span(node: ast.stmt, lines: list[str]) -> tuple[int, int]:
    """(start, end) line indexes, including decorators and the comments directly above the definition."""
    start = node.lineno - 1
    if getattr(node, "decorator_list", None):
        start = min(d.lineno for d in node.decorator_list) - 1
    while start > 0 and lines[start - 1].lstrip().startswith("#"):
        start -= 1
    return start, node.end_lineno


def _is_import(n: ast.stmt) -> bool:
    return isinstance(n, (ast.Import, ast.ImportFrom))


def _is_docstring(n: ast.stmt) -> bool:
    return isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)


def _render_import(key: tuple, name: list[str]) -> str:
    if key[0] == "import":
        return f"import {key[1]}" + (f" as {key[2]}" if key[2] else "")
    module = "." * key[2] + (key[1] or "")
    lines = f"from {module} import {', '.join(name)}"
    if len(lines) <= 110:
        return lines
    body, cur = [], "   "
    for n in name:
        if len(cur) + len(n) + 2 > 100:
            body.append(cur.rstrip())
            cur = "   "
        cur += f" {n},"
    body.append(cur.rstrip())
    return f"from {module} import (\n" + "\n".join(body) + "\n)"


def _group(key: tuple) -> int:
    mod = key[1] or ""
    if mod == "__future__":
        return 0
    if key[0] == "from" and key[2] > 0 or mod.split(".")[0] == "app":
        return 3
    return 1 if mod.split(".")[0] in sys.stdlib_module_names else 2


def merge_imports(src: str, new_imports: list[ast.stmt]) -> str:
    tree, lines = ast.parse(src), src.splitlines()
    body, i = tree.body, 0
    if body and _is_docstring(body[0]):
        i = 1
    old = []
    while i < len(body) and _is_import(body[i]):
        old.append(body[i])
        i += 1
    entries: dict[tuple, list[str]] = {}
    for n in old + new_imports:
        if isinstance(n, ast.Import):
            for a in n.names:
                entries.setdefault(("import", a.name, a.asname), [])
        else:
            listing = entries.setdefault(("from", n.module, n.level), [])
            for a in n.names:
                s = a.name + (f" as {a.asname}" if a.asname else "")
                if s not in listing:
                    listing.append(s)
    groups: dict[int, list[tuple]] = {}
    for k, name in entries.items():
        groups.setdefault(_group(k), []).append(k)
    for g in groups:
        groups[g] = [_render_import(k, sorted(entries[k])) for k in sorted(groups[g], key=lambda k: (k[0] == "from", k[1] or ""))]
    header = "\n\n".join("\n".join(groups[g]) for g in sorted(groups))
    if old:
        start, end = old[0].lineno - 1, old[-1].end_lineno
    else:
        start = end = body[0].end_lineno if body and _is_docstring(body[0]) else 0
        header = ("\n" if start else "") + header + "\n"
    return "\n".join(lines[:start] + header.splitlines() + lines[end:]) + "\n"


def add(old: str, new: str) -> str:
    """Upsert: definitions with the same name are replaced, new ones are appended, imports are merged."""
    tb, lb = ast.parse(new), new.splitlines()
    lines = old.splitlines()
    tl = ast.parse(old) if old.strip() else ast.Module(body=[], type_ignores=[])
    old_positions = {_name(n): _span(n, lines) for n in tl.body if _name(n)}

    replacements, additions, prev_end = [], [], 0
    for n in tb.body:
        if _is_import(n) or _is_docstring(n):
            prev_end = n.end_lineno
            continue
        name = _name(n)
        if name and name in old_positions:
            a, b = _span(n, lb)
            replacements.append((old_positions[name], lb[a:b]))
        else:
            seg = lb[prev_end:n.end_lineno]
            while seg and not seg[0].strip():
                seg.pop(0)
            additions.append(seg)
        prev_end = n.end_lineno

    for (a, b), body in sorted(replacements, key=lambda x: -x[0][0]):
        lines[a:b] = body
    # New definitions go to the end of the file, but BEFORE an `if __name__ == "__main__":` block if there is one.
    tail: list[str] = []
    if additions and "__main__" in old_positions:
        now = ast.parse("\n".join(lines))
        main_start = next(_span(n, lines)[0] for n in now.body if _name(n) == "__main__")
        lines, tail = lines[:main_start], lines[main_start:]
    text = "\n".join(lines).rstrip()
    for seg in additions:
        text += ("\n\n\n" if text else "") + "\n".join(seg)
    if tail:
        text += "\n\n\n" + "\n".join(tail).strip("\n")
    text += "\n"
    imports = [n for n in tb.body if _is_import(n)]
    if imports:
        text = merge_imports(text, imports)
    return tidy(text)


def remove(old: str, names: list[str]) -> str:
    lines = old.splitlines()
    spans = [_span(n, lines) for n in ast.parse(old).body if _name(n) in names]
    if len(spans) != len(names):
        raise SystemExit(f"remove: not all names were found: {names}")
    for a, b in sorted(spans, reverse=True):
        del lines[a:b]
    return tidy("\n".join(lines) + "\n")


def tidy(text: str) -> str:
    return re.sub(r"\n{4,}", "\n\n\n", text).strip("\n") + "\n"


# ----------------------------------------------------------------------------- build _solutions
def build() -> list[int]:
    text = LAB.read_text(encoding="utf-8")
    ops = read_operations(text)
    steps_found = sorted({int(m.group(1)) for b in text.splitlines() if (m := RE_STEP.match(b))} - {0})
    files: dict[str, str] = {"app/__init__.py": ""}
    if SOLUTIONS.exists():
        shutil.rmtree(SOLUTIONS)
    for n in steps_found:
        for (_, op, path, body) in (o for o in ops if o[0] == n):
            if op == "full":
                files[path] = body
            elif op == "add":
                files[path] = add(files.get(path, ""), body)
            else:
                files[path] = remove(files[path], [x.strip() for x in body.split(",")])
            if path.endswith(".py"):
                try:
                    ast.parse(files[path])
                except SyntaxError as e:
                    raise SystemExit(f"Step {n}, {path}: SyntaxError {e}")
        target = SOLUTIONS / f"step-{n:02d}"
        for path, body in files.items():
            f = target / path
            f.parent.mkdir(parents=True, exist_ok=True)
            if path == "langgraph.json":
                body = body.replace('"env": ".env"', '"env": "../../.env"')
            f.write_text(body, encoding="utf-8")
    (SOLUTIONS / "README.md").write_text(
        "# Solutions per step\n\n"
        "This folder is GENERATED from the code blocks in LAB.md (`uv run scripts/build_solutions.py`). Do not edit it by hand.\n\n"
        "- `step-NN/` = the content of `app/`, `app.py`, and `langgraph.json` after step NN.\n"
        "- Run a solution: `cd _solutions/step-05 && uv run app.py \"Process claim CLM-001\"`.\n"
        "- Test a solution: `cd _solutions/step-05 && uv run pytest ../../tests/test_step05.py`.\n"
        "- Compare with your code: `diff -ru _solutions/step-05/app app`.\n",
        encoding="utf-8",
    )
    print(f"_solutions/ built: steps {steps_found}")
    return steps_found


def _tests_for(n: int) -> list[str]:
    return [str(f) for f in sorted((ROOT / "tests").glob("test_step*.py"))
            if int(f.stem.removeprefix("test_step")[:2]) <= n]


def test(step: list[int]) -> bool:
    def run_one(n: int):
        tests = _tests_for(n)
        if not tests:
            return n, True, "(no tests)"
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        env.pop("LLM_API_KEY", None)
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", *tests], cwd=SOLUTIONS / f"step-{n:02d}", env=env,
                           capture_output=True, text=True, timeout=600)
        return n, r.returncode == 0, (r.stdout.strip().splitlines() or ["?"])[-1] if r.returncode == 0 else r.stdout[-3000:]

    ok = True
    with ThreadPoolExecutor(max_workers=4) as ex:
        for n, passed, info in ex.map(run_one, step):
            print(f"step {n:2d}: {'PASSED' if passed else 'FAILED'}  {info if passed else ''}")
            if not passed:
                ok = False
                print(info)
    return ok


# ----------------------------------------------------------------------------- fill example outputs
def _run_command(n: int, command: str, runtime: str) -> str:
    """Run an example command from the folder _solutions/step-NN/ and return its output text.

    Supported: `uv run app.py ...`, `uv run python ...`, `uv run pytest ...`, a VAR=value prefix,
    `cd _solutions/step-NN` (ignored, the command already runs in the solution folder),
    a `> /dev/null` suffix (the command runs, its output is not shown), and a
    `printf '...' | ` prefix (that text is sent to stdin, for chat mode examples).
    """
    folder = SOLUTIONS / f"step-{n:02d}"
    output = []
    for cmd in command.split(" && "):
        if cmd.startswith("cd "):
            continue
        quiet = cmd.endswith(" > /dev/null")          # run it, but do not show the output
        stdin, body = None, cmd.removesuffix(" > /dev/null")
        if m := re.match(r"^printf '([^']*)' \| (.+)$", body):
            stdin, body = m.group(1).replace("\\n", "\n"), m.group(2)
        token = shlex.split(body)
        env = {**os.environ, "RUNTIME_DIR": runtime, "LLM_MODE": "mock", "PYTHONIOENCODING": "utf-8",
               "PYTHONDONTWRITEBYTECODE": "1", "EMBEDDING": "hash", "MAX_REVISIONS": "2", "MOCK_FIRST_DRAFT_INCOMPLETE": "1",
               "HR_FAIL_TIMES": "0", "CRASH_AFTER_PAYMENT": "0", "COLUMNS": "120"}
        env.pop("LLM_API_KEY", None)
        while token and re.match(r"^[A-Z_]+=", token[0]):
            k, v = token.pop(0).split("=", 1)
            env[k] = v
        if token[:2] != ["uv", "run"]:
            raise SystemExit(f"unknown output command: {cmd}")
        if token[2] == "python":
            argv = [sys.executable, *token[3:]]
        elif token[2] == "pytest":
            argv = [sys.executable, "-m", "pytest", *[str(ROOT / a) if a.startswith("tests/") else a for a in token[3:]]]
        else:                                       # uv run app.py ...
            argv = [sys.executable, *token[2:]]
        r = subprocess.run(argv, cwd=folder, env=env, input=stdin, capture_output=True, text=True, timeout=300)
        text = "" if quiet else (r.stdout + r.stderr).rstrip()
        output.append(f"$ {cmd}" + (f"\n{text}" if text else ""))
    result = "\n\n".join(output)
    result = re.sub(r"\bt-[0-9a-f]{6}\b", "t-a1b2c3", result)
    result = re.sub(r"\d+ passed in [\d.]+s", lambda m: m.group(0).split(" in ")[0], result)
    result = result.replace(str(ROOT) + "/", "").replace(runtime, "runtime")
    return result


def fill_outputs() -> None:
    text = LAB.read_text(encoding="utf-8")
    lines = text.splitlines()
    out, i = [], 0
    while i < len(lines):
        m = RE_OUTPUT.match(lines[i].strip())
        out.append(lines[i])
        if not m:
            i += 1
            continue
        j = i + 1
        while lines[j].strip() != "<!-- /output -->":
            j += 1
        n, command, max_len = int(m.group(1)), m.group(2), m.group(3)
        with tempfile.TemporaryDirectory() as rt:
            result = _run_command(n, command, rt)
        b = result.splitlines()
        if max_len and len(b) > int(max_len):
            b = b[: int(max_len)] + [f"… ({len(b) - int(max_len)} more lines truncated)"]
        out += ["```text", *b, "```", "<!-- /output -->"]
        print(f"output step {n}: {command[:60]} ({len(b)} lines)")
        i = j + 1
    LAB.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> None:
    step = build()
    if "--test" in sys.argv and not test(step):
        raise SystemExit(1)
    if "--output" in sys.argv:
        fill_outputs()


if __name__ == "__main__":
    main()

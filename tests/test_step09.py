"""Step 9: evaluating agent behavior with a dataset of cases."""

import importlib.util

import pytest


@pytest.fixture
def evaluate(code_dir):
    spec = importlib.util.spec_from_file_location("evaluate", code_dir / "evaluate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dataset_lengkap(evaluate):
    case = evaluate.load_cases()
    assert len(case) >= 10 and len({k["id"] for k in case}) == len(case)
    assert {"routing", "decision", "tool", "rag"} <= {k["category"] for k in case}


def test_periksa_menemukan_kegagalan(evaluate):
    case = {"expect": {"route": "claim", "action": "reject", "tool": ["claim_details"], "answer_contains": ["X"]}}
    failures = evaluate.check(case, {"route": "policy", "decision": {"action": "reject"}, "answer": "abc"})
    assert len(failures) == 3


def test_mode_mock_skor_penuh(evaluate, capsys):
    assert evaluate.main() == 0
    assert "(100%)" in capsys.readouterr().out

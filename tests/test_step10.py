"""Step 10: fan-out, several nodes in one superstep, join."""

from helpers import superstep_dari, task_per_superstep

from app.graph import build_graph
from app.nodes import check_employee


def test_cek_karyawan():
    out = check_employee({"claim": {"employee_id": "EMP-05"}})
    assert out["profile"]["remaining_budget"] == 400000 and out["profile"]["name"] == "Eko Saputra"


def test_cek_karyawan_paralel_dengan_pemeriksaan_item():
    step = task_per_superstep(build_graph(), {"request": "Process claim CLM-001"})
    s = superstep_dari(step, "check_employee")
    assert any(n in ("check_all_items", "check_item") for n in step[s]), f"must be one superstep: {step}"
    assert sum(n == "decide" for name in step.values() for n in name) == 1, "join: decide runs once"
    assert superstep_dari(step, "decide") == s + 1


def test_tolak_karena_anggaran():
    s = build_graph().invoke({"request": "Process claim CLM-005"})
    k = s["decision"]
    assert (k["action"], k["total_approved"], k["needs_approval"]) == ("reject", 0, False)
    assert "budget" in k["reason"] and s["profile"]["employee_id"] == "EMP-05"


def test_keputusan_semua_klaim():
    expected = {
        "CLM-001": ("approve_partial", 1020000, True),
        "CLM-002": ("approve_full", 180000, False),
        "CLM-003": ("approve_partial", 2100000, True),
        "CLM-004": ("approve_partial", 1030000, True),
        "CLM-005": ("reject", 0, False),
    }
    g = build_graph()
    for cid, (action, total, needs_approval) in expected.items():
        k = g.invoke({"request": f"Proses {cid}"})["decision"]
        assert (k["action"], k["total_approved"], k["needs_approval"]) == (action, total, needs_approval), cid

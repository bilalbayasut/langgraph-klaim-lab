"""Langkah 6: map-reduce dengan Send, input_schema, reducer pengumpul hasil."""

import time

from helpers import superstep_dari, task_per_superstep
from langgraph.types import Send

from app import tools
from app.graph import build_graph
from app.nodes import fan_out_item, periksa_item


def test_fan_out_satu_send_per_item():
    s = {"claim_id": "KLM-003", "klaim": tools.ambil_klaim("KLM-003")}
    sends = fan_out_item(s)
    assert len(sends) == 3 and all(isinstance(x, Send) and x.node == "periksa_item" for x in sends)
    assert sends[0].arg == {"claim_id": "KLM-003", "item": s["klaim"]["item"][0]}


def test_periksa_item_menerima_itemtask():
    item = tools.ambil_klaim("KLM-001")["item"][1]
    out = periksa_item({"claim_id": "KLM-001", "item": item})
    assert out["hasil_item"][0]["status"] == "dipotong" and len(out["hasil_item"]) == 1


def test_semua_periksa_item_dalam_satu_superstep():
    langkah = task_per_superstep(build_graph(), {"permintaan": "Proses klaim KLM-003"})
    s = superstep_dari(langkah, "periksa_item")
    assert langkah[s].count("periksa_item") == 3 and "cek_karyawan" in langkah[s]


def test_reducer_mengumpulkan_hasil():
    s = build_graph().invoke({"permintaan": "Proses klaim KLM-003"})
    assert sorted(h["item_id"] for h in s["hasil_item"]) == ["KLM-003-1", "KLM-003-2", "KLM-003-3"]
    assert [h["item_id"] for h in s["keputusan"]["rincian"]] == ["KLM-003-1", "KLM-003-2", "KLM-003-3"]


def test_benar_benar_paralel(monkeypatch):
    asli = tools.periksa_item

    def lambat(item, kebijakan):
        time.sleep(0.3)
        return asli(item, kebijakan)

    monkeypatch.setattr(tools, "periksa_item", lambat)
    t0 = time.perf_counter()
    build_graph().invoke({"permintaan": "Proses klaim KLM-003"})
    assert time.perf_counter() - t0 < 0.8, "3 item x 0,3 detik harus selesai ~0,3 detik bila paralel"

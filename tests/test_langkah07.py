"""Langkah 7: MCP server terpisah, client MCP, tool MCP dipakai agent."""

import asyncio

from app import mcp_klien
from app.asisten import alat
from app.graph import build_graph


def test_server_menawarkan_tool_lewat_mcp():
    nama = {t.name for t in asyncio.run(mcp_klien.daftar_tool())}
    assert {"profil_karyawan", "detail_klaim"} <= nama


def test_panggil_tool_lewat_mcp():
    hasil = asyncio.run(mcp_klien.panggil_tool("profil_karyawan", {"nama": "Sari"}))
    assert "Rp3.000.000" in hasil and "via MCP" in hasil


def test_tool_mcp_dibungkus_jadi_tool_langchain():
    t = {t.name: t for t in mcp_klien.tool_mcp()}
    assert "nama" in t["profil_karyawan"].args
    assert "via MCP" in t["detail_klaim"].invoke({"claim_id": "KLM-001"})


def test_asisten_memakai_tool_dari_mcp():
    assert {"profil_karyawan", "detail_klaim"} <= {t.name for t in alat()}
    s = build_graph().invoke({"permintaan": "Berapa sisa anggaran Sari?"})
    assert "via MCP" in s["messages"][2].content and "Rp3.000.000" in s["jawaban"]


def test_server_tidak_mengimpor_kode_agent(kode):
    teks = (kode / "mcp_server" / "hr_finance.py").read_text()
    assert "from app" not in teks and "import app" not in teks


def test_app_py_mcp():
    from conftest import app_py

    out = app_py("--mcp").stdout
    assert "profil_karyawan" in out and "detail_klaim" in out


def test_mcp_lewat_streamable_http(monkeypatch, kode):
    """Server dinyalakan sendiri dengan --http; client terhubung lewat MCP_HR_FINANCE_URL."""
    import os
    import socket
    import subprocess
    import sys
    import time

    with socket.socket() as s:                         # cari port kosong
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = subprocess.Popen([sys.executable, str(kode / "mcp_server" / "hr_finance.py"), "--http", "--port", str(port)],
                              env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):                           # tunggu server siap menerima koneksi
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        monkeypatch.setenv("MCP_HR_FINANCE_URL", f"http://127.0.0.1:{port}/mcp")
        assert {"profil_karyawan", "detail_klaim"} <= {t.name for t in asyncio.run(mcp_klien.daftar_tool())}
        hasil = asyncio.run(mcp_klien.panggil_tool("profil_karyawan", {"nama": "Sari"}))
        assert "Rp3.000.000" in hasil
    finally:
        server.terminate()
        server.wait(timeout=10)


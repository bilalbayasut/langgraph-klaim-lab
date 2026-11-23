"""Step 7: separate MCP server, MCP client, MCP tools used by the agent."""

import asyncio

from app import mcp_client
from app.assistant import assistant_tools
from app.graph import build_graph


def test_server_menawarkan_tool_lewat_mcp():
    name = {t.name for t in asyncio.run(mcp_client.list_server_tools())}
    assert {"employee_profile", "claim_details"} <= name


def test_panggil_tool_lewat_mcp():
    result = asyncio.run(mcp_client.call_server_tool("employee_profile", {"name": "Sari"}))
    assert "Rp3.000.000" in result and "via MCP" in result


def test_tool_mcp_dibungkus_jadi_tool_langchain():
    t = {t.name: t for t in mcp_client.mcp_tools()}
    assert "name" in t["employee_profile"].args
    assert "via MCP" in t["claim_details"].invoke({"claim_id": "CLM-001"})


def test_asisten_memakai_tool_dari_mcp():
    assert {"employee_profile", "claim_details"} <= {t.name for t in assistant_tools()}
    s = build_graph().invoke({"request": "Berapa sisa anggaran Sari?"})
    assert "via MCP" in s["messages"][2].content and "Rp3.000.000" in s["answer"]


def test_server_tidak_mengimpor_kode_agent(code_dir):
    text = (code_dir / "mcp_server" / "hr_finance.py").read_text()
    assert "from app" not in text and "import app" not in text


def test_app_py_mcp():
    from conftest import app_py

    out = app_py("--mcp").stdout
    assert "employee_profile" in out and "claim_details" in out


def test_mcp_lewat_streamable_http(monkeypatch, code_dir):
    """The server is started separately with --http; the client connects via MCP_HR_FINANCE_URL."""
    import os
    import socket
    import subprocess
    import sys
    import time

    with socket.socket() as s:                         # find a free port
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = subprocess.Popen([sys.executable, str(code_dir / "mcp_server" / "hr_finance.py"), "--http", "--port", str(port)],
                              env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):                           # wait until the server accepts connections
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        monkeypatch.setenv("MCP_HR_FINANCE_URL", f"http://127.0.0.1:{port}/mcp")
        assert {"employee_profile", "claim_details"} <= {t.name for t in asyncio.run(mcp_client.list_server_tools())}
        result = asyncio.run(mcp_client.call_server_tool("employee_profile", {"name": "Sari"}))
        assert "Rp3.000.000" in result
    finally:
        server.terminate()
        server.wait(timeout=10)



def test_mcp_url_from_settings(monkeypatch):
    """MCP_HR_FINANCE_URL is a setting (Settings.mcp_hr_finance_url); filled = Streamable HTTP, empty = stdio."""
    from app import mcp_client
    from app.config import get_settings

    def connect():
        return mcp_client.connection("hr_finance") if hasattr(mcp_client, "connection") else mcp_client.server_hr()

    monkeypatch.setenv("MCP_HR_FINANCE_URL", "")
    assert get_settings().mcp_hr_finance_url == "" and not isinstance(connect(), str)
    monkeypatch.setenv("MCP_HR_FINANCE_URL", "http://127.0.0.1:8001/mcp")
    assert get_settings().mcp_hr_finance_url == "http://127.0.0.1:8001/mcp"
    assert connect() == "http://127.0.0.1:8001/mcp"

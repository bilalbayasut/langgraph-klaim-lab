"""Step 25: MCP server template for the capstone."""

import asyncio

from mcp import Client

from app.mcp_client import params


def test_template_usecase_bisa_dipakai(code_dir):
    async def check():
        async with Client(params(code_dir / "mcp_server" / "template_usecase.py")) as c:
            tools = {t.name: t for t in (await c.list_tools()).tools}
            result = await c.call_tool("dry_blocks", {"moisture_threshold": 12})
            return tools, result.content[0].text

    tools, text = asyncio.run(check())
    assert {"block_status", "dry_blocks", "schedule_irrigation"} <= set(tools)
    assert tools["schedule_irrigation"].annotations.destructive_hint is True
    assert "B-02" in text

"""Langkah 25: template MCP server untuk capstone."""

import asyncio

from mcp import Client

from app.mcp_klien import params


def test_template_usecase_bisa_dipakai(kode):
    async def cek():
        async with Client(params(kode / "mcp_server" / "template_usecase.py")) as c:
            tools = {t.name: t for t in (await c.list_tools()).tools}
            hasil = await c.call_tool("blok_kekurangan_air", {"batas_kelembapan": 12})
            return tools, hasil.content[0].text

    tools, teks = asyncio.run(cek())
    assert {"kondisi_blok", "blok_kekurangan_air", "jadwalkan_irigasi"} <= set(tools)
    assert tools["jadwalkan_irigasi"].annotations.destructive_hint is True
    assert "B-02" in teks

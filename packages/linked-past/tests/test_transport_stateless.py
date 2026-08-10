"""Stateless Streamable HTTP regression tests (MCP 2026-07-28).

The server must not mint Mcp-Session-Id headers, and must still answer
2025-era handshake-based clients (the SDK bridges the revisions).
"""

import asyncio

import httpx
from linked_past.core.server import build_http_app, create_mcp_server


def test_no_session_id_header(patched_app_context):
    """A legacy initialize POST gets a response with no Mcp-Session-Id header."""

    async def run():
        app = build_http_app(create_mcp_server(), host="testserver")
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.post(
                    "/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-06-18",
                            "capabilities": {},
                            "clientInfo": {"name": "legacy-test", "version": "0"},
                        },
                    },
                    headers={
                        "Accept": "application/json, text/event-stream",
                        "Content-Type": "application/json",
                    },
                )

    response = asyncio.run(run())
    assert response.status_code == 200
    assert "mcp-session-id" not in {k.lower() for k in response.headers}


def test_in_process_client_lists_tools(patched_app_context):
    """The SDK 2.0 in-process client can list tools without any session setup."""
    from mcp.client import Client

    async def run():
        mcp = create_mcp_server()
        async with Client(mcp) as client:
            result = await client.list_tools()
            return [t.name for t in result.tools]

    names = asyncio.run(run())
    assert "discover_datasets" in names
    assert "query" in names

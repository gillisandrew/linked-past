# MCP 2026-07-28 Migration Design

Date: 2026-08-10
Status: Approved

## Goal

Bring the linked-past MCP server up to the current MCP specification revision
(2026-07-28) and eliminate application-layer sessions from the transport.

## Background

The 2026-07-28 spec revision (released two weeks before this design):

- Removes protocol-level sessions and the `Mcp-Session-Id` header from
  Streamable HTTP (SEP-2567). Cross-call state, where needed, becomes explicit
  server-minted handles passed as ordinary tool arguments.
- Makes the protocol stateless: the `initialize`/`notifications/initialized`
  handshake is gone; every request carries its protocol version and client
  capabilities in `_meta`. A mandatory `server/discover` RPC advertises
  supported versions and capabilities (SEP-2575).
- Replaces the HTTP GET stream and `resources/subscribe` with
  `subscriptions/listen`; removes SSE resumability (`Last-Event-ID`);
  removes `ping` and `logging/setLevel`; requires `ttlMs`/`cacheScope` on
  list results; recommends deterministic `tools/list` ordering.
- Deprecates Roots, Sampling, and client Logging.

The Python SDK released `mcp` 2.0.0 on the same day as the revision. It speaks
2026-07-28 natively and still serves 2025-era (handshake-based) clients from
the same `MCPServer` with automatic per-request version handling. The
decorator API is preserved: `FastMCP` is renamed `MCPServer`, and the typed
lifespan / `ctx.request_context.lifespan_context` pattern is unchanged.

## Current state

- `packages/linked-past/linked_past/core/server.py` builds a
  `mcp.server.fastmcp.FastMCP` server (SDK 1.26.0) and runs it with
  `mcp.run(transport="streamable-http")` — stateful, session-ID-based.
- Surface is 14 tools only. No resources, prompts, sampling, elicitation,
  roots, subscriptions, client logging, or progress streams.
- A single shared `AppContext` is built once and yielded by the lifespan to
  every request; it is already session-agnostic.
- The "session log" / viewer sessions are an application domain concept
  (research session reports), not MCP protocol sessions. Unaffected.
- Viewer HTTP/WebSocket routes are injected via the private
  `mcp._custom_starlette_routes` attribute.
- Two test files build the server via `create_mcp_server()`.

## Decision

Upgrade to SDK 2.0 and serve stateless (approach A of three considered;
alternatives were staying on 1.x with `stateless_http=True` — which fails the
"latest revision" requirement — and upgrading while keeping stateful legacy
sessions, which keeps the machinery we want gone).

1. **Dependency**: pin `mcp>=2,<3` in `packages/linked-past/pyproject.toml`.
2. **Server**: import `MCPServer` from `mcp.server`; keep the existing typed
   lifespan; build the ASGI app with
   `mcp.streamable_http_app(stateless_http=True)` and run it under uvicorn
   with the CLI-provided host/port (replacing `mcp.settings.host/port` and
   `mcp.run()`).
3. **Viewer routes**: switch from the private `_custom_starlette_routes`
   attribute to the public `custom_starlette_routes` parameter of
   `streamable_http_app()`. If WebSocket routes are not accepted there,
   fall back to the documented pattern of mounting the MCP app inside a
   parent Starlette application that owns the viewer routes and runs
   `mcp.session_manager.run()` in its lifespan.
4. **Tools**: no signature or body changes. `server/discover`, per-request
   `_meta` versioning, `ttlMs`/`cacheScope`, and deterministic tool ordering
   are SDK responsibilities.
5. **Tests**: update imports/construction in the two affected test files.
   Add a transport regression test asserting (a) responses carry no
   `Mcp-Session-Id` header and (b) a tool call succeeds without any
   initialize handshake.

## Error handling

No new error paths. Version mismatch (`UnsupportedProtocolVersionError`) and
legacy-client bridging are SDK-internal. Input validation errors continue to
surface as tool execution errors per the spec.

## Testing

- Existing suite (410 tests) must pass unchanged apart from the two files
  that construct the server.
- New transport test as above, using the SDK's ASGI test client against
  `streamable_http_app(stateless_http=True)`.

## Out of scope (YAGNI)

Tasks extension, icons metadata, OAuth/authorization changes, MRTR
(no server-initiated requests exist), `subscriptions/listen` (no
subscriptions exist), viewer feature changes.

## Risks

`mcp` 2.0.0 is a day-one major release. Mitigations: our tools-only surface
avoids the reworked feature areas; the full test suite plus the new transport
test gate the PR; the change ships as a single reviewable PR.

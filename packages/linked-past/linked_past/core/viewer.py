"""ViewerManager — WebSocket manager and route handlers for the result feed viewer."""

from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse
from starlette.websockets import WebSocket, WebSocketDisconnect

from linked_past.core.viewer_page import VIEWER_HTML

logger = logging.getLogger(__name__)

# ── Module-level singleton ─────────────────────────────────────────────────────

_manager: ViewerManager | None = None


def get_manager() -> ViewerManager | None:
    """Return the active ViewerManager singleton, or None if unset."""
    return _manager


def set_manager(m: ViewerManager) -> None:
    """Set the module-level ViewerManager singleton."""
    global _manager
    _manager = m


# ── ViewerManager ──────────────────────────────────────────────────────────────


class ViewerManager:
    """Manages WebSocket clients for the live result feed."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._active: bool = False

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        """True when the viewer has been activated."""
        return self._active

    @property
    def client_count(self) -> int:
        """Number of currently connected WebSocket clients."""
        return len(self._clients)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def activate(self) -> None:
        """Mark the viewer as active (start accepting connections)."""
        self._active = True
        logger.debug("ViewerManager activated")

    async def deactivate(self) -> None:
        """Send close frames to all clients, clear the client set, go inactive."""
        for ws in list(self._clients):
            try:
                await ws.close()
            except Exception:
                pass
        self._clients.clear()
        self._active = False
        logger.debug("ViewerManager deactivated")

    # ── Connection management ─────────────────────────────────────────────────

    async def connect(self, ws: WebSocket) -> None:
        """Accept a WebSocket connection and register the client."""
        await ws.accept()
        self._clients.add(ws)
        logger.debug("Viewer client connected (total=%d)", self.client_count)

    async def disconnect(self, ws: WebSocket) -> None:
        """Remove a client from the set."""
        self._clients.discard(ws)
        logger.debug("Viewer client disconnected (total=%d)", self.client_count)

    # ── Broadcasting ──────────────────────────────────────────────────────────

    async def broadcast(self, html_fragment: str) -> None:
        """Send an HTML fragment to all connected clients.

        Failed sends are silently removed from the client set.
        """
        dead: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_text(html_fragment)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)

    # ── URL helper ────────────────────────────────────────────────────────────

    def viewer_url(self, host: str, port: int) -> str:
        """Return the HTTP URL at which the viewer page is served."""
        return f"http://{host}:{port}/viewer"


# ── Route handlers ─────────────────────────────────────────────────────────────


async def viewer_page_handler(request: Request) -> HTMLResponse | PlainTextResponse:  # noqa: ARG001
    """Serve the viewer HTML page, or 404 if the viewer is not active."""
    mgr = get_manager()
    if mgr is None or not mgr.is_active:
        return PlainTextResponse("Viewer not active", status_code=404)
    return HTMLResponse(VIEWER_HTML)


async def viewer_ws_handler(websocket: WebSocket) -> None:
    """Handle a WebSocket connection for the live feed.

    Closes with code 1008 if the viewer is not active.
    """
    mgr = get_manager()
    if mgr is None or not mgr.is_active:
        await websocket.close(code=1008)
        return

    await mgr.connect(websocket)
    try:
        while True:
            # Keep the connection alive; we only push to clients (no pull needed).
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await mgr.disconnect(websocket)

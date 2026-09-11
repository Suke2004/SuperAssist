import asyncio
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional

from .session_manager import session_manager
from .utils import send_json
from .metrics import app_metrics

router = APIRouter()

# Grace period before a disconnected session's STT connection is torn down.
# The frontend retries with exponential backoff (2+4+8+16+32 ~= 62s), so 90s
# comfortably covers every reconnect attempt before cleanup fires.
DISCONNECT_GRACE_SECONDS = 90


def _origin_host_is_local(websocket: WebSocket) -> bool:
    """Allow same-origin browser connections; reject cross-origin pages.

    Browsers always send an ``Origin`` header on WebSocket handshakes, so any
    webpage open on this machine trying to reach ws://127.0.0.1:<port>/ws is
    rejected here (its origin host won't match our Host header). The desktop
    webview loads the app from the same local origin, so its handshake either
    matches or omits Origin entirely (some WebKit builds do) - both allowed.
    """
    origin = websocket.headers.get("origin")
    if not origin:
        return True  # Non-browser client (e.g. tests, pywebview builds)

    try:
        origin_host = urlsplit(origin).hostname
    except ValueError:
        return False
    if not origin_host:
        return False

    host_header = websocket.headers.get("host", "")
    request_host = host_header.split(":", 1)[0].lower()
    return origin_host.lower() == request_host

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: Optional[str] = Query(None)):
    """
    Main WebSocket endpoint. Handles new connections and resumes existing sessions.
    Rejects handshakes from foreign origins (cross-site WebSocket hijacking).
    """
    # --- B6: cross-site WebSocket hijacking protection -------------------
    if not _origin_host_is_local(websocket):
        app_metrics.inc("ws_origins_rejected")
        print(f"Rejected WebSocket connection from foreign origin: {websocket.headers.get('origin')}")
        await websocket.close(code=1008)
        return

    session = None
    if session_id:
        session = session_manager.get_session(session_id)
        if session:
            print(f"🔗 Resuming session: {session_id}")
            session.websocket = websocket
            session.cancel_delayed_cleanup()  # A resumed session must not be torn down
            await websocket.accept()
            await send_json(websocket, "session_resumed", {"session_id": session.session_id})
        else:
            print(f"⚠️ Session not found: {session_id}. Creating new session.")
    
    if not session:
        await websocket.accept()
        session = session_manager.create_session()
        session.websocket = websocket
        await send_json(websocket, "session_created", {"session_id": session.session_id})

    try:
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")
            payload = message.get("payload", {})

            # Route message to the appropriate handler within the session
            handler = getattr(session, f"handle_{message_type}", None)
            if handler:
                try:
                    await handler(payload)
                except Exception as handler_err:
                    print(f"❌ Handler error in session {session.session_id} for '{message_type}': {handler_err}")
                    try:
                        await send_json(websocket, "error", {
                            "message": f"Error processing '{message_type}': {str(handler_err)[:200]}",
                            "type": message_type
                        })
                    except Exception:
                        pass  # Don't crash if we can't send the error
            else:
                print(f"⚠️ Unknown message type: {message_type}")

    except WebSocketDisconnect:
        print(f"WebSocket disconnected from session: {session.session_id}")
        session.websocket = None
        app_metrics.inc("ws_disconnects")
        # A5: schedule cleanup so the Deepgram connection doesn't stay open
        # until the 30-min TTL when the client never comes back.
        session_manager.schedule_delayed_cleanup(session.session_id, DISCONNECT_GRACE_SECONDS)
    except Exception as e:
        print(f"Unhandled WebSocket error in session {session.session_id}: {e}")
        session.websocket = None
        app_metrics.inc("ws_disconnects")
        session_manager.schedule_delayed_cleanup(session.session_id, DISCONNECT_GRACE_SECONDS)
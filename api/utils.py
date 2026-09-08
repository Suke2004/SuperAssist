import orjson
from fastapi import WebSocket

async def send_json(websocket: WebSocket, type: str, payload: dict):
    """
    Helper function to send JSON data to the client with robust error handling.
    Uses orjson for improved serialization performance.
    Checks if the websocket is connected before sending.
    """
    try:
        if websocket.client_state.name == 'CONNECTED':
            # orjson.dumps returns bytes, so we need to decode to string
            json_data = orjson.dumps({"type": type, "payload": payload}).decode('utf-8')
            await websocket.send_text(json_data)
            return True
        else:
            print(f"⚠️ WebSocket not connected, cannot send {type}")
            return False
    except Exception as e:
        print(f"⚠️ Failed to send {type}: {e}")
        return False
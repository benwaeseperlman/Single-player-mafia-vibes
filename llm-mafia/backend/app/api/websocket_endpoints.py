from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from pydantic import UUID4
import uuid # Use standard uuid library

# Import the manager type and the dependency getter
from ..services.websocket_manager import WebSocketManager
from ..dependencies import get_websocket_manager # Import from dependencies.py
# Correct import path if main.py is one level up
# Adjust based on your actual project structure if needed

router = APIRouter()

@router.websocket("/ws/{game_id}/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    game_id: str,
    client_id: str, # Assuming client_id is passed, perhaps player_id
    manager: WebSocketManager = Depends(get_websocket_manager) # Use Depends
):
    """Handles the WebSocket connection for a specific game and client."""
    # Basic validation (could enhance with player ID lookup etc.)
    try:
        # Validate game_id format if necessary (e.g., is it a UUID?)
        uuid.UUID(game_id) # Example validation
        # Validate client_id format if necessary
        uuid.UUID(client_id) # Example validation if client_id is player UUID
    except ValueError:
        print(f"Invalid game_id or client_id format: {game_id}, {client_id}")
        await websocket.close(code=1008) # Policy Violation
        return

    await manager.connect(websocket, game_id)
    try:
        while True:
            # Keep the connection alive, listening for messages (if any)
            # For now, we primarily use this connection for server->client pushes
            # We might add client->server message handling here later (e.g., chat)
            data = await websocket.receive_text()
            # Example: Echo back received data (optional)
            # await websocket.send_text(f"Message text was: {data} from {client_id}")
            print(f"Received from {client_id} in {game_id}: {data}") # Log received messages
            # TODO: Handle incoming messages if needed (e.g., player chat)

    except WebSocketDisconnect:
        manager.disconnect(websocket, game_id)
        print(f"Client {client_id} disconnected from game {game_id}")
    except Exception as e:
        # Log other exceptions
        print(f"Error in WebSocket connection for game {game_id}, client {client_id}: {e}")
        manager.disconnect(websocket, game_id) # Ensure disconnect on error
        # Optionally attempt to close gracefully if possible
        try:
            await websocket.close(code=1011) # Internal Error
        except RuntimeError:
            # WebSocket might already be closed
            pass 
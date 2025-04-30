import asyncio
from fastapi import WebSocket
from pydantic import UUID4
from typing import Dict, List, Set

from ..models import GameState

class WebSocketManager:
    def __init__(self):
        # Maps game_id (str UUID) to a set of WebSocket connections for that game
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, game_id: str):
        """Registers a new WebSocket connection for a given game."""
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = set()
        self.active_connections[game_id].add(websocket)
        print(f"WebSocket connected for game {game_id}. Total connections: {len(self.active_connections[game_id])}")

    def disconnect(self, websocket: WebSocket, game_id: str):
        """Unregisters a WebSocket connection."""
        if game_id in self.active_connections:
            self.active_connections[game_id].remove(websocket)
            print(f"WebSocket disconnected for game {game_id}. Remaining connections: {len(self.active_connections[game_id])}")
            if not self.active_connections[game_id]:
                # Clean up empty set
                del self.active_connections[game_id]
                print(f"Game {game_id} has no active connections.")

    async def broadcast_to_game(self, game_id: str, message: GameState):
        """Broadcasts a message (the GameState) to all clients in a specific game."""
        if game_id in self.active_connections:
            disconnected_sockets = set()
            message_json = message.model_dump_json() # Use model_dump_json for Pydantic V2

            # Create tasks for all sends
            tasks = [
                self._send_personal_message(websocket, message_json)
                for websocket in self.active_connections[game_id]
            ]

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle disconnections based on results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # An error occurred, likely a disconnect
                    websocket = list(self.active_connections[game_id])[i] # Get corresponding socket
                    disconnected_sockets.add(websocket)
                    print(f"Error sending message to a WebSocket in game {game_id}: {result}")

            # Clean up disconnected sockets
            for websocket in disconnected_sockets:
                 # Check if the game_id still exists before trying to remove the websocket
                if game_id in self.active_connections and websocket in self.active_connections[game_id]:
                    self.disconnect(websocket, game_id)

    async def _send_personal_message(self, websocket: WebSocket, message: str):
        """Helper to send a message to a single WebSocket."""
        await websocket.send_text(message)

# Optional: Consider adding methods for broadcasting other types of messages
# e.g., broadcast_error, broadcast_chat_message, etc. if needed later. 
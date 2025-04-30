from .services.websocket_manager import WebSocketManager

# Create a single, shared instance of the WebSocketManager
websocket_manager_instance = WebSocketManager()

def get_websocket_manager() -> WebSocketManager:
    """FastAPI dependency getter for the global WebSocketManager instance."""
    return websocket_manager_instance 
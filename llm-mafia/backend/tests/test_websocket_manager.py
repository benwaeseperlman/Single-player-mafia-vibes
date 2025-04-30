import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect

# Assuming models and manager are accessible via path adjustments or installed package
# Adjust the import path based on your test setup (e.g., using sys.path or pytest config)
from app.services.websocket_manager import WebSocketManager
from app.models import GameState, Player, Role, PlayerStatus, GamePhase, GameSettings


# Fixtures
@pytest.fixture
def manager():
    """Provides a clean WebSocketManager instance for each test."""
    return WebSocketManager()

@pytest.fixture
def mock_websocket():
    """Provides a mock WebSocket object with async methods."""
    # Use MagicMock for spec and AsyncMock for async methods
    ws = MagicMock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.close = AsyncMock()
    return ws

@pytest.fixture
def game_state_fixture() -> GameState:
    """Provides a basic GameState object for testing broadcasts."""
    # Create settings with a UUID and ensure an innocent role
    settings = GameSettings(id=uuid4(), player_count=5, role_distribution={Role.MAFIA: 1, Role.VILLAGER: 4})
    player1 = Player(id=uuid4(), name="p1", role=Role.VILLAGER, status=PlayerStatus.ALIVE, is_human=True)
    player2 = Player(id=uuid4(), name="p2", role=Role.MAFIA, status=PlayerStatus.ALIVE, is_human=False)
    # Add more players to match settings count if needed for other tests, 
    # but for broadcasting, just having a valid GameState object is key.
    players = [player1, player2] 
    # Ensure player list matches player_count if strict validation exists elsewhere
    while len(players) < settings.player_count:
        players.append(Player(id=uuid4(), name=f"p{len(players)+1}", role=Role.VILLAGER, status=PlayerStatus.ALIVE, is_human=False))
        
    return GameState(
        game_id=str(uuid4()),
        players=players, # Use the adjusted player list
        phase=GamePhase.DAY,
        day_number=1,
        settings_id=settings.id, # Use the id from the created settings
        chat_history=[],
        history=[],
        votes={},
        night_actions={}
    )

# Helper to create a mock WebSocket
def create_mock_ws():
    """Creates a new MagicMock instance simulating a WebSocket."""
    ws = MagicMock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.close = AsyncMock()
    return ws

# Tests for WebSocketManager
@pytest.mark.asyncio
async def test_connect_single_client(manager: WebSocketManager, mock_websocket: MagicMock):
    """Test connecting a single client to a game."""
    game_id = "game1"
    await manager.connect(mock_websocket, game_id)
    mock_websocket.accept.assert_awaited_once()
    assert game_id in manager.active_connections
    assert mock_websocket in manager.active_connections[game_id]
    assert len(manager.active_connections[game_id]) == 1

@pytest.mark.asyncio
async def test_connect_multiple_clients_same_game(manager: WebSocketManager):
    """Test connecting multiple clients to the same game."""
    game_id = "game_multi"
    ws1 = create_mock_ws()
    ws2 = create_mock_ws()
    await manager.connect(ws1, game_id)
    await manager.connect(ws2, game_id)
    ws1.accept.assert_awaited_once()
    ws2.accept.assert_awaited_once()
    assert game_id in manager.active_connections
    assert ws1 in manager.active_connections[game_id]
    assert ws2 in manager.active_connections[game_id]
    assert len(manager.active_connections[game_id]) == 2

@pytest.mark.asyncio
async def test_connect_multiple_games(manager: WebSocketManager):
    """Test connecting clients to different games."""
    game_id1 = "game_a"
    game_id2 = "game_b"
    ws_a = create_mock_ws()
    ws_b = create_mock_ws()
    await manager.connect(ws_a, game_id1)
    await manager.connect(ws_b, game_id2)
    assert game_id1 in manager.active_connections
    assert ws_a in manager.active_connections[game_id1]
    assert len(manager.active_connections[game_id1]) == 1
    assert game_id2 in manager.active_connections
    assert ws_b in manager.active_connections[game_id2]
    assert len(manager.active_connections[game_id2]) == 1

@pytest.mark.asyncio
async def test_disconnect_client(manager: WebSocketManager, mock_websocket: MagicMock):
    """Test disconnecting a client, removing the game entry."""
    game_id = "game_disconnect"
    await manager.connect(mock_websocket, game_id)
    assert game_id in manager.active_connections
    manager.disconnect(mock_websocket, game_id)
    # Since it was the only client, the game_id key should be removed
    assert game_id not in manager.active_connections

@pytest.mark.asyncio
async def test_disconnect_one_of_multiple(manager: WebSocketManager):
    """Test disconnecting one client when multiple are connected."""
    game_id = "game_multi_disconnect"
    ws1 = create_mock_ws()
    ws2 = create_mock_ws()
    await manager.connect(ws1, game_id)
    await manager.connect(ws2, game_id)
    assert len(manager.active_connections[game_id]) == 2
    manager.disconnect(ws1, game_id)
    assert game_id in manager.active_connections
    assert ws1 not in manager.active_connections[game_id]
    assert ws2 in manager.active_connections[game_id]
    assert len(manager.active_connections[game_id]) == 1

@pytest.mark.asyncio
async def test_disconnect_nonexistent_game(manager: WebSocketManager, mock_websocket: MagicMock):
    """Test disconnecting from a game_id that doesn't exist."""
    manager.disconnect(mock_websocket, "nonexistent_game")
    # Should not raise an error and state should be unchanged
    assert "nonexistent_game" not in manager.active_connections

@pytest.mark.asyncio
async def test_disconnect_nonexistent_client_in_game(manager: WebSocketManager, mock_websocket: MagicMock):
    """Test disconnecting a specific websocket not present in an existing game raises KeyError."""
    game_id = "game_exists"
    ws_real = create_mock_ws()
    await manager.connect(ws_real, game_id)
    initial_connections = manager.active_connections[game_id].copy()
    
    # Attempt to disconnect a different websocket mock
    # This should raise KeyError because mock_websocket is not in the set
    with pytest.raises(KeyError):
        manager.disconnect(mock_websocket, game_id)
        
    # Assert the original connection is still present
    assert game_id in manager.active_connections
    assert manager.active_connections[game_id] == initial_connections
    assert ws_real in manager.active_connections[game_id]
    assert mock_websocket not in manager.active_connections[game_id]
    assert len(manager.active_connections[game_id]) == 1


@pytest.mark.asyncio
async def test_broadcast_to_game(manager: WebSocketManager, game_state_fixture: GameState):
    """Test broadcasting a message to all clients in a specific game."""
    game_id = game_state_fixture.game_id
    ws1 = create_mock_ws()
    ws2 = create_mock_ws()
    await manager.connect(ws1, game_id)
    await manager.connect(ws2, game_id)
    message_json = game_state_fixture.model_dump_json()
    await manager.broadcast_to_game(game_id, game_state_fixture)
    ws1.send_text.assert_awaited_once_with(message_json)
    ws2.send_text.assert_awaited_once_with(message_json)

@pytest.mark.asyncio
async def test_broadcast_to_empty_game(manager: WebSocketManager, game_state_fixture: GameState):
    """Test broadcasting to a game with no clients (should not error or send)."""
    game_id = game_state_fixture.game_id
    # Patch the helper send method to ensure it's never called
    with patch.object(manager, '_send_personal_message', new_callable=AsyncMock) as mock_send:
        await manager.broadcast_to_game(game_id, game_state_fixture)
        mock_send.assert_not_awaited()

@pytest.mark.asyncio
async def test_broadcast_with_disconnection(manager: WebSocketManager, game_state_fixture: GameState):
    """Test broadcasting handles exceptions during sending and disconnects the faulty client."""
    game_id = game_state_fixture.game_id
    ws1_connected = create_mock_ws()
    ws2_disconnected = create_mock_ws()
    # Simulate ws2 disconnecting by raising an error during send_text
    ws2_disconnected.send_text.side_effect = ConnectionRefusedError("Simulated disconnect")
    await manager.connect(ws1_connected, game_id)
    await manager.connect(ws2_disconnected, game_id)
    assert len(manager.active_connections[game_id]) == 2

    message_json = game_state_fixture.model_dump_json()
    await manager.broadcast_to_game(game_id, game_state_fixture)

    # Assert ws1 (connected) received the message
    ws1_connected.send_text.assert_awaited_once_with(message_json)
    # Assert ws2 (disconnected) send was attempted
    ws2_disconnected.send_text.assert_awaited_once_with(message_json)

    # Assert ws2 was automatically disconnected by the broadcast method's error handling
    assert game_id in manager.active_connections
    assert ws1_connected in manager.active_connections[game_id]
    assert ws2_disconnected not in manager.active_connections[game_id]
    assert len(manager.active_connections[game_id]) == 1

@pytest.mark.asyncio
async def test_broadcast_to_multiple_games(manager: WebSocketManager, game_state_fixture: GameState):
    """Test broadcasting only sends to clients in the specified game."""
    game_id1 = game_state_fixture.game_id
    game_id2 = "other_game"
    ws1 = create_mock_ws()
    ws2 = create_mock_ws()
    ws_other = create_mock_ws() # Client for the other game
    await manager.connect(ws1, game_id1)
    await manager.connect(ws2, game_id1)
    await manager.connect(ws_other, game_id2)

    message_json = game_state_fixture.model_dump_json()
    await manager.broadcast_to_game(game_id1, game_state_fixture)

    # Game 1 clients should receive the message
    ws1.send_text.assert_awaited_once_with(message_json)
    ws2.send_text.assert_awaited_once_with(message_json)

    # Game 2 client should NOT receive the message
    ws_other.send_text.assert_not_awaited()
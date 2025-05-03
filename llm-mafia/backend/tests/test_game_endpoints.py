import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock # Use AsyncMock for async methods
import uuid
import random
from uuid import UUID

# Add the project root to the Python path
# This is often necessary for tests to find the app module
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app  # Import the FastAPI app
from app.models.game import GameState, GamePhase
from app.models.player import Player, Role, PlayerStatus
from app.models.settings import GameSettings
from app.models.actions import ActionType, ChatMessage # Import ActionType, ChatMessage
# Import ActionValidationError for testing exceptions
from app.services.action_service import ActionValidationError
# We will patch the game_manager instance *where it is used* (in game_endpoints)
# from app.services.game_manager import GameManager
# We will patch state_service where it is used
# from app.services import state_service

# Use FastAPI's TestClient
client = TestClient(app)

# --- Test Data --- 
def create_mock_game_state(game_id: str, settings_id: uuid.UUID, player_count: int = 5, phase: GamePhase = GamePhase.NIGHT) -> GameState:
    """Helper to create a consistent mock GameState. Assumes 1 Mafia, 1 Detective, 1 Doctor, rest Villagers for default 5 players."""
    # Basic role assignment for mock state consistency
    roles = [Role.MAFIA, Role.DETECTIVE, Role.DOCTOR] + [Role.VILLAGER] * (player_count - 3)
    if len(roles) != player_count:
        roles = [Role.VILLAGER] * player_count # Fallback just in case
    random.shuffle(roles)

    players = []
    human_assigned = False
    for i in range(player_count):
        is_human = not human_assigned
        players.append(
             Player(id=str(uuid.uuid4()), name=f"Player {i+1}" if not is_human else "You", role=roles[i], status=PlayerStatus.ALIVE, is_human=is_human)
        )
        if is_human:
            human_assigned = True
    if not human_assigned and players: # Ensure human player
        players[0].is_human = True

    return GameState(
        game_id=game_id,
        settings_id=settings_id,
        players=players,
        phase=phase,
        day_number=1,
        history=[],
        night_actions={},
        votes={}
    )

# --- Tests --- 

# Patch the game_manager instance within the game_endpoints module
@patch('app.api.game_endpoints.game_manager', new_callable=MagicMock)
def test_create_new_game(mock_manager):
    """Test POST /api/game endpoint."""
    mock_settings_id = uuid.uuid4()
    mock_game_id = str(uuid.uuid4())
    # Use a valid player count
    test_player_count = 5
    mock_game_state = create_mock_game_state(mock_game_id, mock_settings_id, test_player_count)

    # Configure the mock manager's method (no longer async)
    mock_manager.create_game.return_value = mock_game_state

    # Use string keys for roles and valid player count
    settings_payload = {
        "id": str(mock_settings_id),
        "player_count": test_player_count,
        "role_distribution": {
            Role.MAFIA.value: 1,
            Role.DETECTIVE.value: 1,
            Role.DOCTOR.value: 1,
            Role.VILLAGER.value: test_player_count - 3 # Ensure total matches player_count
        }
    }

    # TestClient handles async functions correctly
    response = client.post("/api/game", json=settings_payload)

    # Assert status code *first*
    assert response.status_code == 201, f"Expected 201 but got {response.status_code}. Response: {response.text}"

    response_data = response.json()
    assert response_data["game_id"] == mock_game_id
    assert response_data["settings_id"] == str(mock_settings_id)
    # Check player count matches the response (may differ from input if model adjusted)
    assert len(response_data["players"]) == test_player_count
    mock_manager.create_game.assert_called_once()
    # Check if the Pydantic model was passed correctly
    call_args, _ = mock_manager.create_game.call_args
    assert isinstance(call_args[0], GameSettings)
    assert call_args[0].id == mock_settings_id
    assert call_args[0].player_count == test_player_count

# Patch the game_manager instance within the game_endpoints module
@patch('app.api.game_endpoints.game_manager', new_callable=MagicMock)
def test_get_game_by_id_success(mock_manager):
    """Test GET /api/game/{game_id} endpoint successfully retrieves game."""
    mock_game_id = str(uuid.uuid4())
    mock_settings_id = uuid.uuid4()
    mock_game_state = create_mock_game_state(mock_game_id, mock_settings_id)

    # Configure the mock manager's method (no longer async)
    mock_manager.get_game.return_value = mock_game_state

    response = client.get(f"/api/game/{mock_game_id}")

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["game_id"] == mock_game_id
    mock_manager.get_game.assert_called_once_with(mock_game_id)

# Patch the game_manager instance within the game_endpoints module
@patch('app.api.game_endpoints.game_manager', new_callable=MagicMock)
def test_get_game_by_id_not_found(mock_manager):
    """Test GET /api/game/{game_id} returns 404 for non-existent game."""
    non_existent_id = str(uuid.uuid4())

    # Mock the GameManager instance and its get_game method to return None
    mock_manager.get_game.return_value = None

    response = client.get(f"/api/game/{non_existent_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": f"Game with ID {non_existent_id} not found"}
    mock_manager.get_game.assert_called_once_with(non_existent_id)


def test_get_game_by_id_invalid_uuid():
    """Test GET /api/game/{game_id} returns 400 for invalid UUID format."""
    invalid_id = "not-a-uuid"
    # No mock needed as the endpoint should validate the path parameter format
    response = client.get(f"/api/game/{invalid_id}")
    assert response.status_code == 400
    assert response.json() == {"detail": f"Invalid game ID format: {invalid_id}"}

# Patch the state_service module where it is used (in game_endpoints)
@patch('app.api.game_endpoints.state_service', new_callable=MagicMock)
def test_list_all_games(mock_state_service):
    """Test GET /api/games endpoint."""
    mock_game_uuids = [uuid.uuid4(), uuid.uuid4()]
    # Configure the mock service's method (no longer async)
    mock_state_service.list_saved_games.return_value = mock_game_uuids

    response = client.get("/api/games")

    assert response.status_code == 200
    # The endpoint should convert UUIDs to strings
    assert response.json() == [str(gid) for gid in mock_game_uuids]
    mock_state_service.list_saved_games.assert_called_once()

# Patch the state_service module where it is used (in game_endpoints)
@patch('app.api.game_endpoints.state_service', new_callable=MagicMock)
def test_list_all_games_empty(mock_state_service):
    """Test GET /api/games endpoint when no games exist."""
    # Configure the mock service's method (no longer async)
    mock_state_service.list_saved_games.return_value = []

    response = client.get("/api/games")

    assert response.status_code == 200
    assert response.json() == []
    mock_state_service.list_saved_games.assert_called_once()

# --- Tests for Player Action Endpoints (Step 14) ---

# Test POST /api/game/{game_id}/action
@patch('app.api.game_endpoints.game_manager', new_callable=AsyncMock)
@patch('app.api.game_endpoints.action_service', new_callable=MagicMock)
def test_submit_action_success(mock_action_service, mock_game_manager):
    """Test successfully submitting a night action."""
    mock_game_id = str(uuid.uuid4())
    mock_settings_id = uuid.uuid4()
    mock_game_state = create_mock_game_state(mock_game_id, mock_settings_id, phase=GamePhase.NIGHT)
    detective = next(p for p in mock_game_state.players if p.role == Role.DETECTIVE)
    target = next(p for p in mock_game_state.players if p.id != detective.id)

    mock_game_manager.get_game.return_value = mock_game_state
    # Configure action_service mock (it doesn't return anything on success)
    mock_action_service.record_night_action.return_value = None

    action_payload = {
        "player_id": str(detective.id),
        "target_id": str(target.id),
        "action_type": ActionType.DETECTIVE_INVESTIGATE.value
    }

    response = client.post(f"/api/game/{mock_game_id}/action", json=action_payload)

    assert response.status_code == 204
    mock_game_manager.get_game.assert_awaited_once_with(mock_game_id)
    mock_action_service.record_night_action.assert_called_once_with(
        mock_game_state,
        detective.id,
        target.id,
        ActionType.DETECTIVE_INVESTIGATE
    )

@patch('app.api.game_endpoints.game_manager', new_callable=AsyncMock)
def test_submit_action_wrong_phase(mock_game_manager):
    """Test submitting action during the wrong phase (Day)."""
    mock_game_id = str(uuid.uuid4())
    mock_settings_id = uuid.uuid4()
    # Create game state in DAY phase
    mock_game_state = create_mock_game_state(mock_game_id, mock_settings_id, phase=GamePhase.DAY)
    player = mock_game_state.players[0]
    target = mock_game_state.players[1]

    mock_game_manager.get_game.return_value = mock_game_state

    action_payload = {
        "player_id": str(player.id),
        "target_id": str(target.id),
        "action_type": ActionType.MAFIA_KILL.value
    }

    response = client.post(f"/api/game/{mock_game_id}/action", json=action_payload)

    assert response.status_code == 400
    assert "Actions can only be submitted during the Night phase" in response.json()["detail"]
    mock_game_manager.get_game.assert_awaited_once_with(mock_game_id)

@patch('app.api.game_endpoints.game_manager', new_callable=AsyncMock)
@patch('app.api.game_endpoints.action_service', new_callable=MagicMock)
def test_submit_action_validation_error(mock_action_service, mock_game_manager):
    """Test submitting an action that fails action_service validation."""
    mock_game_id = str(uuid.uuid4())
    mock_settings_id = uuid.uuid4()
    mock_game_state = create_mock_game_state(mock_game_id, mock_settings_id, phase=GamePhase.NIGHT)
    player = mock_game_state.players[0] # Assume this player has already acted
    target = mock_game_state.players[1]

    mock_game_manager.get_game.return_value = mock_game_state
    # Configure action_service to raise ActionValidationError
    error_message = "Player has already performed their action this night."
    mock_action_service.record_night_action.side_effect = ActionValidationError(error_message)

    action_payload = {
        "player_id": str(player.id),
        "target_id": str(target.id),
        "action_type": ActionType.DETECTIVE_INVESTIGATE.value # Action type doesn't matter here
    }

    response = client.post(f"/api/game/{mock_game_id}/action", json=action_payload)

    assert response.status_code == 400
    assert response.json() == {"detail": error_message}
    mock_game_manager.get_game.assert_awaited_once_with(mock_game_id)
    mock_action_service.record_night_action.assert_called_once()


# Test POST /api/game/{game_id}/message
@patch('app.api.game_endpoints.game_manager', new_callable=AsyncMock) # GameManager methods are now async
@patch('app.api.game_endpoints.get_websocket_manager', new_callable=MagicMock) # Mock the dependency getter
def test_submit_message_success(mock_get_ws_manager, mock_game_manager):
    """Test successfully submitting a chat message."""
    mock_game_id = str(uuid.uuid4())
    mock_settings_id = uuid.uuid4()
    # Create game state in DAY phase
    mock_game_state = create_mock_game_state(mock_game_id, mock_settings_id, phase=GamePhase.DAY)
    human_player = next(p for p in mock_game_state.players if p.is_human)

    mock_game_manager.get_game.return_value = mock_game_state
    # Mock the update_game_state method to return True (success)
    mock_game_manager.update_game_state.return_value = True
    # Mock the WebSocket manager instance (it's not used directly in assertions here)
    mock_ws_manager = MagicMock()
    mock_get_ws_manager.return_value = mock_ws_manager

    message_payload = {
        "player_id": str(human_player.id),
        "message": "This is a test message!"
    }

    response = client.post(f"/api/game/{mock_game_id}/message", json=message_payload)

    assert response.status_code == 204
    mock_game_manager.get_game.assert_called_once_with(mock_game_id)
    # Assert update_game_state was called
    mock_game_manager.update_game_state.assert_awaited_once()
    # Check the updated state passed to update_game_state
    call_args, _ = mock_game_manager.update_game_state.call_args
    updated_state = call_args[1] # Second argument is the new_state
    assert isinstance(updated_state, GameState)
    assert len(updated_state.chat_history) == 1
    assert updated_state.chat_history[0].player_id == human_player.id
    assert updated_state.chat_history[0].message == message_payload["message"]


@patch('app.api.game_endpoints.game_manager', new_callable=AsyncMock)
def test_submit_message_wrong_phase(mock_game_manager):
    """Test submitting message during the wrong phase (Night)."""
    mock_game_id = str(uuid.uuid4())
    mock_settings_id = uuid.uuid4()
    # Create game state in NIGHT phase
    mock_game_state = create_mock_game_state(mock_game_id, mock_settings_id, phase=GamePhase.NIGHT)
    human_player = next(p for p in mock_game_state.players if p.is_human)

    mock_game_manager.get_game.return_value = mock_game_state

    message_payload = {
        "player_id": str(human_player.id),
        "message": "Trying to speak at night..."
    }

    response = client.post(f"/api/game/{mock_game_id}/message", json=message_payload)

    assert response.status_code == 400
    assert "Messages can only be sent during the Day phase" in response.json()["detail"]
    mock_game_manager.get_game.assert_awaited_once_with(mock_game_id)
    mock_game_manager.update_game_state.assert_not_called()

@patch('app.api.game_endpoints.game_manager', new_callable=AsyncMock)
def test_submit_message_dead_player(mock_game_manager):
    """Test submitting message from a dead player."""
    mock_game_id = str(uuid.uuid4())
    mock_settings_id = uuid.uuid4()
    mock_game_state = create_mock_game_state(mock_game_id, mock_settings_id, phase=GamePhase.DAY)
    human_player = next(p for p in mock_game_state.players if p.is_human)
    human_player.status = PlayerStatus.DEAD # Make the human player dead

    mock_game_manager.get_game.return_value = mock_game_state

    message_payload = {
        "player_id": str(human_player.id),
        "message": "Message from the grave?"
    }

    response = client.post(f"/api/game/{mock_game_id}/message", json=message_payload)

    assert response.status_code == 400
    assert "Dead players cannot send messages" in response.json()["detail"]
    mock_game_manager.get_game.assert_awaited_once_with(mock_game_id)

@patch('app.api.game_endpoints.game_manager', new_callable=AsyncMock)
def test_submit_message_ai_player(mock_game_manager):
    """Test submitting message from an AI player via API (should be forbidden)."""
    mock_game_id = str(uuid.uuid4())
    mock_settings_id = uuid.uuid4()
    mock_game_state = create_mock_game_state(mock_game_id, mock_settings_id, phase=GamePhase.DAY)
    ai_player = next(p for p in mock_game_state.players if not p.is_human)

    mock_game_manager.get_game.return_value = mock_game_state

    message_payload = {
        "player_id": str(ai_player.id),
        "message": "AI trying to use the human API."
    }

    response = client.post(f"/api/game/{mock_game_id}/message", json=message_payload)

    assert response.status_code == 403
    assert "Only human players can submit messages via this endpoint" in response.json()["detail"]
    mock_game_manager.get_game.assert_awaited_once_with(mock_game_id)


# Test POST /api/game/{game_id}/vote
@patch('app.api.game_endpoints.game_manager', new_callable=AsyncMock)
def test_submit_vote_success(mock_game_manager):
    """Test successfully submitting a vote."""
    mock_game_id = str(uuid.uuid4())
    mock_settings_id = uuid.uuid4()
    mock_game_state = create_mock_game_state(mock_game_id, mock_settings_id, phase=GamePhase.VOTING)
    human_player = next(p for p in mock_game_state.players if p.is_human)
    target_player = next(p for p in mock_game_state.players if p.id != human_player.id and p.status == PlayerStatus.ALIVE)

    mock_game_manager.get_game.return_value = mock_game_state
    mock_game_manager.update_game_state.return_value = True

    vote_payload = {
        "player_id": str(human_player.id),
        "target_id": str(target_player.id)
    }

    response = client.post(f"/api/game/{mock_game_id}/vote", json=vote_payload)

    assert response.status_code == 204
    mock_game_manager.get_game.assert_awaited_once_with(mock_game_id)
    mock_game_manager.update_game_state.assert_awaited_once()
    # Check the updated state passed to update_game_state
    call_args, _ = mock_game_manager.update_game_state.call_args
    updated_state = call_args[1] # Second argument is the new_state
    assert isinstance(updated_state, GameState)
    assert str(human_player.id) in updated_state.votes
    assert updated_state.votes[str(human_player.id)] == str(target_player.id)

@patch('app.api.game_endpoints.game_manager', new_callable=AsyncMock)
def test_submit_vote_wrong_phase(mock_game_manager):
    """Test submitting vote during the wrong phase (Day)."""
    mock_game_id = str(uuid.uuid4())
    mock_settings_id = uuid.uuid4()
    mock_game_state = create_mock_game_state(mock_game_id, mock_settings_id, phase=GamePhase.DAY) # Wrong phase
    human_player = next(p for p in mock_game_state.players if p.is_human)
    target_player = next(p for p in mock_game_state.players if p.id != human_player.id)

    mock_game_manager.get_game.return_value = mock_game_state

    vote_payload = {
        "player_id": str(human_player.id),
        "target_id": str(target_player.id)
    }

    response = client.post(f"/api/game/{mock_game_id}/vote", json=vote_payload)

    assert response.status_code == 400
    assert "Votes can only be submitted during the Voting phase" in response.json()["detail"]
    mock_game_manager.get_game.assert_awaited_once_with(mock_game_id)
    mock_game_manager.update_game_state.assert_not_called()

@patch('app.api.game_endpoints.game_manager', new_callable=AsyncMock)
def test_submit_vote_dead_voter(mock_game_manager):
    """Test submitting vote from a dead player."""
    mock_game_id = str(uuid.uuid4())
    mock_settings_id = uuid.uuid4()
    mock_game_state = create_mock_game_state(mock_game_id, mock_settings_id, phase=GamePhase.VOTING)
    human_player = next(p for p in mock_game_state.players if p.is_human)
    human_player.status = PlayerStatus.DEAD # Make voter dead
    target_player = next(p for p in mock_game_state.players if p.id != human_player.id and p.status == PlayerStatus.ALIVE)

    mock_game_manager.get_game.return_value = mock_game_state

    vote_payload = {
        "player_id": str(human_player.id),
        "target_id": str(target_player.id)
    }

    response = client.post(f"/api/game/{mock_game_id}/vote", json=vote_payload)

    assert response.status_code == 400
    assert "Dead players cannot vote" in response.json()["detail"]
    mock_game_manager.get_game.assert_awaited_once_with(mock_game_id)

@patch('app.api.game_endpoints.game_manager', new_callable=AsyncMock)
def test_submit_vote_dead_target(mock_game_manager):
    """Test submitting vote for a dead player."""
    mock_game_id = str(uuid.uuid4())
    mock_settings_id = uuid.uuid4()
    mock_game_state = create_mock_game_state(mock_game_id, mock_settings_id, phase=GamePhase.VOTING)
    human_player = next(p for p in mock_game_state.players if p.is_human)
    target_player = next(p for p in mock_game_state.players if p.id != human_player.id)
    target_player.status = PlayerStatus.DEAD # Make target dead

    mock_game_manager.get_game.return_value = mock_game_state

    vote_payload = {
        "player_id": str(human_player.id),
        "target_id": str(target_player.id)
    }

    response = client.post(f"/api/game/{mock_game_id}/vote", json=vote_payload)

    assert response.status_code == 400
    assert "Cannot vote for a dead player" in response.json()["detail"]
    mock_game_manager.get_game.assert_awaited_once_with(mock_game_id)

@patch('app.api.game_endpoints.game_manager', new_callable=AsyncMock)
def test_submit_vote_ai_voter(mock_game_manager):
    """Test submitting vote from an AI player via API (should be forbidden)."""
    mock_game_id = str(uuid.uuid4())
    mock_settings_id = uuid.uuid4()
    mock_game_state = create_mock_game_state(mock_game_id, mock_settings_id, phase=GamePhase.VOTING)
    ai_voter = next(p for p in mock_game_state.players if not p.is_human)
    target_player = next(p for p in mock_game_state.players if p.id != ai_voter.id and p.status == PlayerStatus.ALIVE)

    mock_game_manager.get_game.return_value = mock_game_state

    vote_payload = {
        "player_id": str(ai_voter.id),
        "target_id": str(target_player.id)
    }

    response = client.post(f"/api/game/{mock_game_id}/vote", json=vote_payload)

    assert response.status_code == 403
    assert "Only human players can submit votes via this endpoint" in response.json()["detail"]
    mock_game_manager.get_game.assert_awaited_once_with(mock_game_id) 
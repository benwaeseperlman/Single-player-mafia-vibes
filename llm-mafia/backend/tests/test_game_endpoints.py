import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock  # Use MagicMock for sync methods
import uuid
import random

# Add the project root to the Python path
# This is often necessary for tests to find the app module
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app  # Import the FastAPI app
from app.models.game import GameState, GamePhase
from app.models.player import Player, Role, PlayerStatus
from app.models.settings import GameSettings
# We will patch the game_manager instance *where it is used* (in game_endpoints)
# from app.services.game_manager import GameManager
# We will patch state_service where it is used
# from app.services import state_service

# Use FastAPI's TestClient
client = TestClient(app)

# --- Test Data --- 
def create_mock_game_state(game_id: str, settings_id: uuid.UUID, player_count: int = 5) -> GameState:
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
        phase=GamePhase.NIGHT,
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
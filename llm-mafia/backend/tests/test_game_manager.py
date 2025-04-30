import pytest
from unittest.mock import patch, MagicMock, call, AsyncMock
import sys
import os
from uuid import UUID, uuid4

# --- Path Hack --- 
# Add the backend directory to sys.path to allow relative imports
# Get the absolute path of the current test file
test_file_path = os.path.abspath(__file__)
# Get the directory containing the test file (tests/)
test_dir = os.path.dirname(test_file_path)
# Get the directory containing the tests directory (backend/)
backend_dir = os.path.dirname(test_dir)
# Add backend directory to sys.path if not already present
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
# --- End Path Hack ---


# Revert to relative imports
from app.services.game_manager import GameManager
from app.models import (
    GameSettings,
    GameState,
    Player,
    Role,
    PlayerStatus,
    GamePhase,
)
# Import WebSocketManager for mocking
from app.services.websocket_manager import WebSocketManager

# --- Fixtures ---

@pytest.fixture
def mock_state_service():
    """Mocks the state_service module."""
    # Patch within the game_manager module where it's imported
    with patch('app.services.game_manager.state_service', autospec=True) as mock_service:
        mock_service.save_game_state = MagicMock()
        mock_service.load_game_state = MagicMock(return_value=None)
        mock_service.delete_game_state = MagicMock()
        yield mock_service

@pytest.fixture
def mock_websocket_manager():
    """Mocks the get_websocket_manager function imported in game_manager."""
    # Patch the get_websocket_manager function in the dependencies module
    # because that's what game_manager.py calls.
    with patch('app.dependencies.get_websocket_manager') as mock_getter:
        # Configure the mock getter to return an AsyncMock instance
        mock_instance = AsyncMock(spec=WebSocketManager)
        mock_instance.broadcast_to_game = AsyncMock() # Ensure the method is async
        mock_getter.return_value = mock_instance
        yield mock_instance # Yield the *mock instance* for tests to use

@pytest.fixture
def game_manager(mock_state_service, mock_websocket_manager): # Add mock_websocket_manager dependency
    # GameManager itself doesn't need the mock injected at init,
    # but the tests using it will benefit from the patch being active.
    return GameManager()

@pytest.fixture
def sample_game_settings():
    return GameSettings(
        id=uuid4(), # Ensure settings have an ID
        player_count=7,
        role_distribution={Role.MAFIA: 2, Role.DETECTIVE: 1, Role.DOCTOR: 1}
    )

@pytest.fixture
def sample_game_state(sample_game_settings):
    game_uuid_str = str(uuid4())
    players = [
        Player(id=uuid4(), name="P1", role=Role.MAFIA, status=PlayerStatus.ALIVE, is_human=True, persona_id=None),
        Player(id=uuid4(), name="P2", role=Role.MAFIA, status=PlayerStatus.ALIVE, is_human=False, persona_id=None),
        Player(id=uuid4(), name="P3", role=Role.DETECTIVE, status=PlayerStatus.ALIVE, is_human=False, persona_id=None),
        Player(id=uuid4(), name="P4", role=Role.DOCTOR, status=PlayerStatus.ALIVE, is_human=False, persona_id=None),
        Player(id=uuid4(), name="P5", role=Role.VILLAGER, status=PlayerStatus.ALIVE, is_human=False, persona_id=None),
        Player(id=uuid4(), name="P6", role=Role.VILLAGER, status=PlayerStatus.ALIVE, is_human=False, persona_id=None),
        Player(id=uuid4(), name="P7", role=Role.VILLAGER, status=PlayerStatus.ALIVE, is_human=False, persona_id=None),
    ]
    return GameState(
        game_id=game_uuid_str, # Use string ID
        players=players,
        phase=GamePhase.NIGHT,
        day_number=0,
        settings_id=sample_game_settings.id,
        history=[],
        night_actions={},
        votes={}
    )


# --- Test Cases ---

def test_create_game_success(game_manager, mock_state_service, sample_game_settings):
    created_state = game_manager.create_game(sample_game_settings)
    assert isinstance(created_state, GameState)
    # Assert that the game_id attribute is actually a UUID object
    assert isinstance(created_state.game_id, UUID)
    # Check if it's a valid UUID string by trying to convert it (Old assertion)
    # try:
    #     UUID(created_state.game_id) # This would fail as created_state.game_id is already UUID
    #     is_valid_uuid_string = True
    # except ValueError:
    #     is_valid_uuid_string = False
    # assert is_valid_uuid_string

    assert len(created_state.players) == sample_game_settings.player_count
    assert created_state.phase == GamePhase.NIGHT
    assert created_state.day_number == 0
    assert created_state.settings_id == sample_game_settings.id
    roles_created = [p.role for p in created_state.players]
    assert roles_created.count(Role.MAFIA) == 2
    assert roles_created.count(Role.DETECTIVE) == 1
    assert roles_created.count(Role.DOCTOR) == 1
    assert roles_created.count(Role.VILLAGER) == 3
    human_players = [p for p in created_state.players if p.is_human]
    assert len(human_players) == 1
    assert human_players[0].name == "You"
    # Assert save was called with the string representation of the game ID
    mock_state_service.save_game_state.assert_called_once_with(str(created_state.game_id), created_state)
    # Assert game is cached with the string representation of the game ID
    # (GameManager uses string internally now for the cache key)
    assert str(created_state.game_id) in game_manager.active_games
    assert game_manager.active_games[str(created_state.game_id)] == created_state

def test_assign_roles_invalid_distribution(game_manager):
    invalid_dist = {Role.MAFIA: 5, Role.DETECTIVE: 3}
    with pytest.raises(ValueError, match="Role distribution exceeds player count."):
        game_manager._assign_roles(player_count=7, role_distribution=invalid_dist)

def test_get_game_cache_hit(game_manager, mock_state_service, sample_game_state):
    game_id_str = sample_game_state.game_id
    game_manager.active_games[game_id_str] = sample_game_state # Cache uses string ID

    retrieved_game = game_manager.get_game(game_id_str)

    assert retrieved_game == sample_game_state
    mock_state_service.load_game_state.assert_not_called()

def test_get_game_cache_miss_load_success(game_manager, mock_state_service, sample_game_state):
    game_id_str = sample_game_state.game_id
    # load_game_state is mocked to return the state when called with the string ID
    mock_state_service.load_game_state.return_value = sample_game_state

    retrieved_game = game_manager.get_game(game_id_str)

    assert retrieved_game == sample_game_state
    mock_state_service.load_game_state.assert_called_once_with(game_id_str) # Assert load called with string ID
    assert game_id_str in game_manager.active_games # Check cache uses string ID
    assert game_manager.active_games[game_id_str] == sample_game_state

def test_get_game_cache_miss_load_fail(game_manager, mock_state_service):
    game_id_str = str(uuid4())
    mock_state_service.load_game_state.return_value = None

    retrieved_game = game_manager.get_game(game_id_str)

    assert retrieved_game is None
    mock_state_service.load_game_state.assert_called_once_with(game_id_str) # Assert load called with string ID
    assert game_id_str not in game_manager.active_games

def test_get_game_invalid_uuid_format(game_manager, mock_state_service):
    # get_game now expects string, so format validation might happen elsewhere
    # Assuming get_game passes the string to load_game_state
    retrieved_game = game_manager.get_game("not-a-uuid")
    assert retrieved_game is None # Should still fail if load_game_state expects UUID internally or fails
    # Check if load was called, depends on load_game_state implementation detail
    mock_state_service.load_game_state.assert_called_once_with("not-a-uuid")

def test_get_game_load_exception(game_manager, mock_state_service):
    game_id_str = str(uuid4())
    mock_state_service.load_game_state.side_effect = Exception("Disk read error")

    retrieved_game = game_manager.get_game(game_id_str)

    assert retrieved_game is None
    mock_state_service.load_game_state.assert_called_once_with(game_id_str) # Assert load called with string ID
    assert game_id_str not in game_manager.active_games

@pytest.mark.asyncio # Mark test as async
async def test_update_game_state_success(game_manager, mock_state_service, mock_websocket_manager, sample_game_state):
    game_id_str = sample_game_state.game_id
    game_manager.active_games[game_id_str] = sample_game_state # Cache uses string ID

    updated_state = sample_game_state.model_copy(deep=True)
    updated_state.day_number = 1
    updated_state.phase = GamePhase.DAY

    result = await game_manager.update_game_state(game_id_str, updated_state) # Await the async function

    assert result is True
    mock_state_service.save_game_state.assert_called_once_with(game_id_str, updated_state) # Assert save called with string ID
    assert game_manager.active_games[game_id_str] == updated_state # Check cache uses string ID
    # Assert broadcast was called
    mock_websocket_manager.broadcast_to_game.assert_awaited_once_with(game_id_str, updated_state)

@pytest.mark.asyncio # Mark test as async
async def test_update_game_state_id_mismatch(game_manager, mock_state_service, mock_websocket_manager, sample_game_state):
    game_id_str = sample_game_state.game_id
    mismatched_state = sample_game_state.model_copy(deep=True)
    mismatched_state.game_id = str(uuid4()) # Ensure it's a different string UUID

    result = await game_manager.update_game_state(game_id_str, mismatched_state) # Await

    assert result is False
    mock_state_service.save_game_state.assert_not_called()
    mock_websocket_manager.broadcast_to_game.assert_not_awaited() # Broadcast should not happen

@pytest.mark.asyncio # Mark test as async
async def test_update_game_state_invalid_uuid_format(game_manager, mock_state_service, mock_websocket_manager, sample_game_state):
    # Assuming update_game_state handles invalid format early
    result = await game_manager.update_game_state("not-a-uuid", sample_game_state) # Await
    assert result is False # Should fail validation or ID mismatch
    mock_state_service.save_game_state.assert_not_called()
    mock_websocket_manager.broadcast_to_game.assert_not_awaited()

@pytest.mark.asyncio # Mark test as async
async def test_update_game_state_save_fail(game_manager, mock_state_service, mock_websocket_manager, sample_game_state):
    game_id_str = sample_game_state.game_id
    game_manager.active_games[game_id_str] = sample_game_state # Cache uses string ID

    updated_state = sample_game_state.model_copy(deep=True)
    updated_state.day_number = 1

    mock_state_service.save_game_state.side_effect = Exception("Disk write error")

    result = await game_manager.update_game_state(game_id_str, updated_state) # Await

    assert result is False
    mock_state_service.save_game_state.assert_called_once_with(game_id_str, updated_state) # Assert save called with string ID
    # Even if save fails, broadcast might still be attempted depending on implementation
    # The current implementation calls broadcast *after* save, within the try block
    # So if save fails, broadcast won't be reached.
    mock_websocket_manager.broadcast_to_game.assert_not_awaited()

@pytest.mark.asyncio # Mark test as async
async def test_update_game_state_broadcast_fail(game_manager, mock_state_service, mock_websocket_manager, sample_game_state):
    """Test update_game_state when broadcasting fails (should still return False)."""
    game_id_str = sample_game_state.game_id
    game_manager.active_games[game_id_str] = sample_game_state

    updated_state = sample_game_state.model_copy(deep=True)
    updated_state.day_number = 1

    # Make broadcast fail
    mock_websocket_manager.broadcast_to_game.side_effect = Exception("WebSocket error")

    result = await game_manager.update_game_state(game_id_str, updated_state)

    assert result is False # Should return False because the overall operation failed
    # Save should have been called before broadcast
    mock_state_service.save_game_state.assert_called_once_with(game_id_str, updated_state)
    # Broadcast should have been awaited
    mock_websocket_manager.broadcast_to_game.assert_awaited_once_with(game_id_str, updated_state)
    # Cache should still be updated because it happens before broadcast
    assert game_manager.active_games[game_id_str] == updated_state

def test_remove_game_from_cache(game_manager, sample_game_state):
    game_id_str = sample_game_state.game_id
    game_manager.active_games[game_id_str] = sample_game_state # Cache uses string ID

    assert game_id_str in game_manager.active_games
    game_manager.remove_game_from_cache(game_id_str)
    assert game_id_str not in game_manager.active_games

def test_remove_game_from_cache_invalid_uuid(game_manager):
    # remove_game_from_cache uses string internally now
    initial_cache = game_manager.active_games.copy()
    game_manager.remove_game_from_cache("not-a-uuid")
    assert game_manager.active_games == initial_cache

def test_remove_game_from_cache_non_existent(game_manager):
    game_id_str = str(uuid4())
    initial_cache = game_manager.active_games.copy()
    game_manager.remove_game_from_cache(game_id_str)
    assert game_manager.active_games == initial_cache 
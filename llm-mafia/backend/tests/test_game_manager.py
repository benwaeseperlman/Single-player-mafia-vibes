import pytest
from unittest.mock import patch, MagicMock, call
import sys
import os
from uuid import UUID, uuid4 # Import UUID and uuid4 directly

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

# --- Fixtures ---

@pytest.fixture
def mock_state_service():
    """Mocks the state_service module."""
    with patch('app.services.game_manager.state_service', autospec=True) as mock_service:
        mock_service.save_game_state = MagicMock()
        mock_service.load_game_state = MagicMock(return_value=None)
        mock_service.delete_game_state = MagicMock()
        yield mock_service

@pytest.fixture
def game_manager(mock_state_service):
    return GameManager()

@pytest.fixture
def sample_game_settings():
    return GameSettings(
        player_count=7,
        role_distribution={Role.MAFIA: 2, Role.DETECTIVE: 1, Role.DOCTOR: 1}
    )

@pytest.fixture
def sample_game_state(sample_game_settings):
    game_uuid = uuid4()
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
        game_id=game_uuid,
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
    assert isinstance(created_state.game_id, UUID)
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
    # Assert save was called with UUID
    mock_state_service.save_game_state.assert_called_once_with(created_state.game_id, created_state)
    # Assert game is cached with UUID
    assert created_state.game_id in game_manager.active_games
    assert game_manager.active_games[created_state.game_id] == created_state

def test_assign_roles_invalid_distribution(game_manager):
    invalid_dist = {Role.MAFIA: 5, Role.DETECTIVE: 3}
    with pytest.raises(ValueError, match="Role distribution exceeds player count."):
        game_manager._assign_roles(player_count=7, role_distribution=invalid_dist)

def test_get_game_cache_hit(game_manager, mock_state_service, sample_game_state):
    game_uuid = sample_game_state.game_id
    game_id_str = str(game_uuid)
    game_manager.active_games[game_uuid] = sample_game_state # Cache uses UUID

    retrieved_game = game_manager.get_game(game_id_str) # Call with string

    assert retrieved_game == sample_game_state
    mock_state_service.load_game_state.assert_not_called()

def test_get_game_cache_miss_load_success(game_manager, mock_state_service, sample_game_state):
    game_uuid = sample_game_state.game_id
    game_id_str = str(game_uuid)
    mock_state_service.load_game_state.return_value = sample_game_state

    retrieved_game = game_manager.get_game(game_id_str) # Call with string

    assert retrieved_game == sample_game_state
    mock_state_service.load_game_state.assert_called_once_with(game_uuid) # Assert load called with UUID
    assert game_uuid in game_manager.active_games # Check cache uses UUID
    assert game_manager.active_games[game_uuid] == sample_game_state

def test_get_game_cache_miss_load_fail(game_manager, mock_state_service):
    game_id_str = str(uuid4())
    game_uuid = UUID(game_id_str)
    mock_state_service.load_game_state.return_value = None

    retrieved_game = game_manager.get_game(game_id_str) # Call with string

    assert retrieved_game is None
    mock_state_service.load_game_state.assert_called_once_with(game_uuid) # Assert load called with UUID
    assert game_uuid not in game_manager.active_games

def test_get_game_invalid_uuid_format(game_manager, mock_state_service):
    """Test get_game returns None for invalid UUID string."""
    retrieved_game = game_manager.get_game("not-a-uuid")
    assert retrieved_game is None
    mock_state_service.load_game_state.assert_not_called()

def test_get_game_load_exception(game_manager, mock_state_service):
    game_id_str = str(uuid4())
    game_uuid = UUID(game_id_str)
    mock_state_service.load_game_state.side_effect = Exception("Disk read error")

    retrieved_game = game_manager.get_game(game_id_str) # Call with string

    assert retrieved_game is None
    mock_state_service.load_game_state.assert_called_once_with(game_uuid) # Assert load called with UUID
    assert game_uuid not in game_manager.active_games

def test_update_game_state_success(game_manager, mock_state_service, sample_game_state):
    game_uuid = sample_game_state.game_id
    game_id_str = str(game_uuid)
    game_manager.active_games[game_uuid] = sample_game_state # Cache uses UUID

    updated_state = sample_game_state.model_copy(deep=True)
    updated_state.day_number = 1
    updated_state.phase = GamePhase.DAY

    result = game_manager.update_game_state(game_id_str, updated_state) # Call with string

    assert result is True
    mock_state_service.save_game_state.assert_called_once_with(game_uuid, updated_state) # Assert save called with UUID
    assert game_manager.active_games[game_uuid] == updated_state # Check cache uses UUID

def test_update_game_state_id_mismatch(game_manager, mock_state_service, sample_game_state):
    game_id_str = str(sample_game_state.game_id)
    mismatched_state = sample_game_state.model_copy(deep=True)
    mismatched_state.game_id = uuid4()

    result = game_manager.update_game_state(game_id_str, mismatched_state) # Call with string

    assert result is False
    mock_state_service.save_game_state.assert_not_called()

def test_update_game_state_invalid_uuid_format(game_manager, mock_state_service, sample_game_state):
    """Test update_game_state returns False for invalid UUID string."""
    result = game_manager.update_game_state("not-a-uuid", sample_game_state)
    assert result is False
    mock_state_service.save_game_state.assert_not_called()

def test_update_game_state_save_fail(game_manager, mock_state_service, sample_game_state):
    game_uuid = sample_game_state.game_id
    game_id_str = str(game_uuid)
    game_manager.active_games[game_uuid] = sample_game_state # Cache uses UUID

    updated_state = sample_game_state.model_copy(deep=True)
    updated_state.day_number = 1

    mock_state_service.save_game_state.side_effect = Exception("Disk write error")

    result = game_manager.update_game_state(game_id_str, updated_state) # Call with string

    assert result is False
    mock_state_service.save_game_state.assert_called_once_with(game_uuid, updated_state) # Assert save called with UUID

def test_remove_game_from_cache(game_manager, sample_game_state):
    game_uuid = sample_game_state.game_id
    game_id_str = str(game_uuid)
    game_manager.active_games[game_uuid] = sample_game_state # Cache uses UUID

    assert game_uuid in game_manager.active_games
    game_manager.remove_game_from_cache(game_id_str) # Call with string
    assert game_uuid not in game_manager.active_games

def test_remove_game_from_cache_invalid_uuid(game_manager):
    """Test remove_game_from_cache ignores invalid UUID string."""
    initial_cache = game_manager.active_games.copy()
    game_manager.remove_game_from_cache("not-a-uuid")
    assert game_manager.active_games == initial_cache # Cache should be unchanged

def test_remove_game_from_cache_non_existent(game_manager):
    """Test removing non-existent game doesn't raise error or change cache."""
    game_id_str = str(uuid4())
    initial_cache = game_manager.active_games.copy()
    game_manager.remove_game_from_cache(game_id_str) # Call with valid but non-cached UUID string
    assert game_manager.active_games == initial_cache # Cache should be unchanged 
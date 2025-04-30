import pytest
import json
import os
from pathlib import Path
import shutil
from unittest.mock import patch
import uuid

# Adjust the path to import from the app directory
# This assumes tests/ is parallel to app/ inside backend/
import sys
APP_PATH = Path(__file__).resolve().parent.parent.parent / 'app'
sys.path.insert(0, str(APP_PATH.parent)) # Add backend/ to sys.path

from app.models.game import GameState, GamePhase
from app.models.player import Player, Role, PlayerStatus
from app.models.settings import GameSettings
from app.services import state_service

# Define a temporary directory for test data
TEST_DATA_DIR = Path(__file__).resolve().parent / "temp_test_data"

# Dummy data for testing
DUMMY_SETTINGS = GameSettings(player_count=7, role_distribution={Role.MAFIA: 2, Role.VILLAGER: 5})
DUMMY_PLAYER_1 = Player(id=uuid.uuid4(), name="Player 1", role=Role.MAFIA, status=PlayerStatus.ALIVE, is_human=False)
DUMMY_PLAYER_2 = Player(id=uuid.uuid4(), name="Human Player", role=Role.VILLAGER, status=PlayerStatus.ALIVE, is_human=True)

# Generate a UUID for the test game ID
DUMMY_GAME_ID_UUID = uuid.uuid4()
DUMMY_GAME_ID_STR = str(DUMMY_GAME_ID_UUID)

DUMMY_GAME_STATE = GameState(
    game_id=DUMMY_GAME_ID_UUID, # Use the UUID object here
    players=[DUMMY_PLAYER_1, DUMMY_PLAYER_2],
    phase=GamePhase.NIGHT,
    day_number=1,
    settings_id=DUMMY_SETTINGS.id, # Corrected: Use settings_id field
    history=[]
)

# Pytest fixture for setting up and tearing down the test directory
@pytest.fixture(scope="module")
def setup_test_directory():
    """Creates and cleans up the temporary directory for the test module."""
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR) # Clean up if leftover
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Created test directory: {TEST_DATA_DIR}") # Added print for visibility
    yield # Let tests run
    # Teardown: Remove the directory after all tests in the module have run
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)
        print(f"Removed test directory: {TEST_DATA_DIR}") # Added print for visibility

# Test functions using pytest style
# Note: Patching DATA_DIR within the state_service module remains the same

@patch('app.services.state_service.DATA_DIR', TEST_DATA_DIR)
def test_save_game_state(setup_test_directory): # Inject the fixture
    """Test saving a valid game state."""
    state_service.save_game_state(DUMMY_GAME_STATE)
    # Use the string representation of the UUID for the filename
    expected_file = TEST_DATA_DIR / f"game_{DUMMY_GAME_ID_STR}.json"
    assert expected_file.exists()

    # Verify content (basic check)
    with open(expected_file, 'r') as f:
        data = json.load(f)
    assert data['game_id'] == DUMMY_GAME_ID_STR # ID is saved as string in JSON
    assert data['phase'] == DUMMY_GAME_STATE.phase.value # Enum is saved as value
    assert len(data['players']) == len(DUMMY_GAME_STATE.players)
    # Compare string representations of UUIDs
    assert data['players'][0]['id'] == str(DUMMY_PLAYER_1.id)
    assert data['players'][0]['role'] == DUMMY_PLAYER_1.role.value
    assert data['players'][0]['status'] == DUMMY_PLAYER_1.status.value # Also check status serialization

@patch('app.services.state_service.DATA_DIR', TEST_DATA_DIR)
def test_load_game_state_success(setup_test_directory): # Inject the fixture
    """Test loading a previously saved game state."""
    # Ensure the file exists (save it first)
    state_service.save_game_state(DUMMY_GAME_STATE)

    # Load using the string representation of the ID
    loaded_state = state_service.load_game_state(DUMMY_GAME_ID_STR)
    assert loaded_state is not None
    # Use Pydantic's equality check
    assert loaded_state == DUMMY_GAME_STATE
    assert loaded_state.phase == GamePhase.NIGHT
    assert loaded_state.players[1].name == "Human Player"

@patch('app.services.state_service.DATA_DIR', TEST_DATA_DIR)
def test_load_game_state_not_found(setup_test_directory): # Inject the fixture
    """Test loading a game state that does not exist."""
    loaded_state = state_service.load_game_state("non_existent_game")
    assert loaded_state is None

@patch('app.services.state_service.DATA_DIR', TEST_DATA_DIR)
def test_load_game_state_corrupted_json(setup_test_directory): # Inject the fixture
    """Test loading a game state from a corrupted JSON file."""
    game_id = "corrupted_game_id_string" # Need a distinct string ID here
    file_path = TEST_DATA_DIR / f"game_{game_id}.json"
    # Ensure the directory exists via the fixture before writing
    with open(file_path, 'w') as f:
        f.write("{ this is not valid json, ")

    # Load using the string ID
    loaded_state = state_service.load_game_state(game_id)
    assert loaded_state is None
    # Clean up the corrupted file
    os.remove(file_path)

@patch('app.services.state_service.DATA_DIR', TEST_DATA_DIR)
def test_delete_game_state_success(setup_test_directory): # Inject the fixture
    """Test deleting an existing game state file."""
    # Ensure the file exists
    state_service.save_game_state(DUMMY_GAME_STATE)
    # Use string ID for filename check
    file_path = TEST_DATA_DIR / f"game_{DUMMY_GAME_ID_STR}.json"
    assert file_path.exists()

    # Delete using the string ID
    result = state_service.delete_game_state(DUMMY_GAME_ID_STR)
    assert result is True
    assert not file_path.exists()

@patch('app.services.state_service.DATA_DIR', TEST_DATA_DIR)
def test_delete_game_state_not_found(setup_test_directory): # Inject the fixture
    """Test deleting a game state file that does not exist."""
    result = state_service.delete_game_state("non_existent_for_delete")
    # Deleting a non-existent file is considered successful (idempotent)
    assert result is True 
import json
import os
from pathlib import Path
from typing import Optional

from app.models.game import GameState

# Define the base path for storing game data relative to this file's location
# Assumes services/ is one level down from app/ and data/ is parallel to app/
# Adjust if directory structure changes
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

def _get_game_state_file_path(game_id: str) -> Path:
    """Constructs the full path for a game state file."""
    # Ensure the data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / f"game_{game_id}.json"

def save_game_state(game_state: GameState) -> None:
    """Saves the current game state to a JSON file.

    Args:
        game_state: The GameState object to save.
    """
    file_path = _get_game_state_file_path(game_state.game_id)
    try:
        # Use Pydantic's serialization capabilities if available and preferred,
        # otherwise default json dump. model_dump_json is available in Pydantic v2+
        if hasattr(game_state, 'model_dump_json'):
            json_data = game_state.model_dump_json(indent=2)
        else:
            # Fallback for older Pydantic versions or different serialization needs
            # This requires custom handling for complex types like Enums or Path objects if not natively supported by json
            # For simplicity, assuming Pydantic models handle this correctly via dict() or custom encoders might be needed
            # json_data = json.dumps(game_state.dict(), indent=2, default=str) # Example for Pydantic v1
            # Since we use Pydantic v2, model_dump_json is the way.
            # If using standard json.dumps, ensure all types are serializable
            # For now, we stick to model_dump_json as it's the modern Pydantic way
            json_data = game_state.model_dump_json(indent=2) # Redundant but ensures clarity

        with open(file_path, "w") as f:
            f.write(json_data)
        print(f"Game state for game {game_state.game_id} saved successfully to {file_path}")
    except IOError as e:
        print(f"Error saving game state for game {game_state.game_id}: {e}")
        # Consider raising an exception or logging more formally
    except Exception as e:
        # Catch other potential errors during serialization or file writing
        print(f"An unexpected error occurred while saving game state {game_state.game_id}: {e}")


def load_game_state(game_id: str) -> Optional[GameState]:
    """Loads a game state from a JSON file.

    Args:
        game_id: The unique identifier for the game to load.

    Returns:
        The loaded GameState object, or None if the file doesn't exist
        or an error occurs during loading/parsing.
    """
    file_path = _get_game_state_file_path(game_id)
    if not file_path.exists():
        print(f"No saved state found for game {game_id}.")
        return None

    try:
        with open(file_path, "r") as f:
            json_data = json.load(f)
            # Use Pydantic's parsing capabilities
            game_state = GameState.model_validate(json_data)
            print(f"Game state for game {game_id} loaded successfully.")
            return game_state
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON for game {game_id}: {e}")
        # Consider logging this error, potentially deleting/archiving the corrupt file
        return None
    except IOError as e:
        print(f"Error reading game state file for game {game_id}: {e}")
        return None
    except Exception as e:
        # Catch other potential errors during file reading or Pydantic validation
        print(f"An unexpected error occurred while loading game state {game_id}: {e}")
        return None

def delete_game_state(game_id: str) -> bool:
    """Deletes the saved state file for a given game ID.

    Args:
        game_id: The unique identifier for the game state to delete.

    Returns:
        True if the file was successfully deleted or didn't exist, False otherwise.
    """
    file_path = _get_game_state_file_path(game_id)
    if not file_path.exists():
        print(f"No saved state file to delete for game {game_id}.")
        return True # Nothing to delete, operation is successful in a sense

    try:
        os.remove(file_path)
        print(f"Game state file for game {game_id} deleted successfully.")
        return True
    except OSError as e:
        print(f"Error deleting game state file for game {game_id}: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while deleting game state file {game_id}: {e}")
        return False

# Example Usage (Optional - Can be removed or kept for testing)
if __name__ == "__main__":
    # This block allows testing the service functions directly if needed
    # Requires creating dummy GameState objects according to your models/game.py definition
    print("State service module loaded. Define dummy GameState and test functions.")
    # Example:
    # from app.models import GameState, Player, Role, PlayerStatus, GamePhase, GameSettings # Adjust imports as needed
    # test_settings = GameSettings(player_count=5, role_distribution={'MAFIA': 1, 'VILLAGER': 4})
    # test_player = Player(id="player1", name="Test Player", role=Role.VILLAGER, status=PlayerStatus.ALIVE, is_human=True)
    # test_game = GameState(game_id="test123", players=[test_player], phase=GamePhase.PREGAME, day_number=0, settings=test_settings)
    # save_game_state(test_game)
    # loaded_game = load_game_state("test123")
    # if loaded_game:
    #     print(f"Loaded game: {loaded_game.game_id}, Phase: {loaded_game.phase}")
    # delete_game_state("test123") 
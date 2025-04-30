import json
import os
from pathlib import Path
from typing import Optional
from uuid import UUID # Import UUID for type checking if needed

from app.models.game import GameState

# Define the base path for storing game data relative to this file's location
# Assumes services/ is one level down from app/ and data/ is parallel to app/
# Adjust if directory structure changes
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

def _get_game_state_file_path(game_id_str: str) -> Path:
    """Constructs the full path for a game state file using a string ID."""
    # Ensure the data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / f"game_{game_id_str}.json"

def save_game_state(game_id_str: str, game_state: GameState) -> None:
    """Saves the current game state to a JSON file, identified by a string ID.

    Args:
        game_id_str: The string representation of the game's UUID.
        game_state: The GameState object to save.
    """
    # Ensure the game_id in the state matches the provided string ID
    if str(game_state.game_id) != game_id_str:
         print(f"Error: Mismatch between provided game_id_str '{game_id_str}' and game_state.game_id '{game_state.game_id}'. Aborting save.")
         # Optionally raise an error
         # raise ValueError("Game ID mismatch during save operation")
         return

    file_path = _get_game_state_file_path(game_id_str)
    try:
        # Use Pydantic's model_dump_json for serialization
        json_data = game_state.model_dump_json(indent=2)

        with open(file_path, "w") as f:
            f.write(json_data)
        print(f"Game state for game {game_id_str} saved successfully to {file_path}")
    except IOError as e:
        print(f"Error saving game state for game {game_id_str}: {e}")
        # Consider raising an exception or logging more formally
    except Exception as e:
        # Catch other potential errors during serialization or file writing
        print(f"An unexpected error occurred while saving game state {game_id_str}: {e}")


def load_game_state(game_id_str: str) -> Optional[GameState]:
    """Loads a game state from a JSON file using a string ID.

    Args:
        game_id_str: The unique string identifier for the game to load.

    Returns:
        The loaded GameState object, or None if the file doesn't exist
        or an error occurs during loading/parsing.
    """
    file_path = _get_game_state_file_path(game_id_str)
    if not file_path.exists():
        print(f"No saved state found for game {game_id_str}.")
        return None

    try:
        with open(file_path, "r") as f:
            json_data = json.load(f)
            # Use Pydantic's parsing capabilities
            game_state = GameState.model_validate(json_data)
            # Verify the loaded state's ID matches the requested ID
            if str(game_state.game_id) != game_id_str:
                print(f"Warning: Loaded game state ID '{game_state.game_id}' does not match requested ID '{game_id_str}'. File: {file_path}")
                # Depending on requirements, you might return None or raise an error here
                # return None
            print(f"Game state for game {game_id_str} loaded successfully.")
            return game_state
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON for game {game_id_str}: {e}")
        # Consider logging this error, potentially deleting/archiving the corrupt file
        return None
    except IOError as e:
        print(f"Error reading game state file for game {game_id_str}: {e}")
        return None
    except Exception as e:
        # Catch other potential errors during file reading or Pydantic validation
        print(f"An unexpected error occurred while loading game state {game_id_str}: {e}")
        return None

def delete_game_state(game_id_str: str) -> bool:
    """Deletes the saved state file for a given string game ID.

    Args:
        game_id_str: The unique string identifier for the game state to delete.

    Returns:
        True if the file was successfully deleted or didn't exist, False otherwise.
    """
    file_path = _get_game_state_file_path(game_id_str)
    if not file_path.exists():
        print(f"No saved state file to delete for game {game_id_str}.")
        return True # Nothing to delete, operation is successful in a sense

    try:
        os.remove(file_path)
        print(f"Game state file for game {game_id_str} deleted successfully.")
        return True
    except OSError as e:
        print(f"Error deleting game state file for game {game_id_str}: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while deleting game state file {game_id_str}: {e}")
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
    # save_game_state("test123", test_game)
    # loaded_game = load_game_state("test123")
    # if loaded_game:
    #     print(f"Loaded game: {loaded_game.game_id}, Phase: {loaded_game.phase}")
    # delete_game_state("test123") 
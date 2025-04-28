import random
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from ..models import (
    GameSettings,
    GameState,
    Player,
    Role,
    PlayerStatus,
    GamePhase,
    AIPersona,  # Assuming personas might be assigned here later
)
from . import state_service

# Basic Persona IDs for now - replace with actual loading/generation later
DEFAULT_PERSONA_IDS = ["persona_logical", "persona_quiet", "persona_aggressive"]

class GameManager:
    """Manages active game instances and interacts with state persistence."""

    def __init__(self):
        self.active_games: Dict[str, GameState] = {}
        # TODO: Potentially load existing games from data directory on startup?

    def _generate_game_id(self) -> str:
        """Generates a unique game ID."""
        return str(uuid4())

    def _assign_roles(self, player_count: int, role_distribution: Dict[Role, int]) -> List[Role]:
        """Assigns roles based on distribution, ensuring exact counts."""
        roles: List[Role] = []
        for role, count in role_distribution.items():
            roles.extend([role] * count)

        # Fill remaining slots with Villagers if distribution doesn't sum to player_count
        # This logic might need refinement based on stricter validation in GameSettings
        current_role_count = len(roles)
        villager_count = player_count - current_role_count
        if villager_count < 0:
             # This should ideally be caught by GameSettings validation
            raise ValueError("Role distribution exceeds player count.")
        roles.extend([Role.VILLAGER] * villager_count)

        if len(roles) != player_count:
             # Fallback validation
             raise ValueError(f"Final role count {len(roles)} does not match player count {player_count}.")

        random.shuffle(roles)
        return roles

    def create_game(self, settings: GameSettings) -> GameState:
        """Creates a new game, assigns roles, saves initial state, and caches it."""
        game_id = self._generate_game_id()

        assigned_roles = self._assign_roles(settings.player_count, settings.role_distribution)

        players: List[Player] = []
        human_player_assigned = False
        for i in range(settings.player_count):
            # Assign one player as human, the rest as AI
            is_human = not human_player_assigned
            player_name = f"Player {i + 1}" if not is_human else "You" # Simple naming for now
            persona_id = None # Assign None for now until Persona management is implemented

            players.append(
                Player(
                    id=str(uuid4()),
                    name=player_name,
                    role=assigned_roles[i],
                    status=PlayerStatus.ALIVE,
                    is_human=is_human,
                    persona_id=persona_id,
                )
            )
            if is_human:
                human_player_assigned = True

        # Ensure at least one human player exists if the logic above somehow fails
        if not human_player_assigned and players:
             players[0].is_human = True
             players[0].name = "You"
             players[0].persona_id = None


        initial_state = GameState(
            game_id=game_id,
            players=players,
            phase=GamePhase.NIGHT, # Start directly in the first Night phase
            day_number=0, # Night 0 / Day 1 convention
            settings_id=settings.id, # Correct: Assign the UUID of the settings object
            history=[], # Initialize empty history
            night_actions={}, # Correct field name from model
            votes={} # Correct field name from model
        )

        try:
            # Use correct relative path for state service assuming it's in the same directory
            state_service.save_game_state(initial_state.game_id, initial_state)
            self.active_games[initial_state.game_id] = initial_state
            print(f"Game {initial_state.game_id} created and saved.") # Logging
            return initial_state
        except Exception as e:
            # Log the error appropriately
            print(f"Error saving game state for new game {initial_state.game_id}: {e}")
            # Should we clean up the file if save fails partially? Consider implications.
            raise # Re-raise the exception after logging

    def get_game(self, game_id_str: str) -> Optional[GameState]:
        """Retrieves game state, checking cache first, then loading from storage."""
        try:
            game_uuid = UUID(game_id_str)
        except ValueError:
            print(f"Invalid game ID format: {game_id_str}") # Logging
            return None # Invalid UUID format

        if game_uuid in self.active_games:
            print(f"Game {game_uuid} found in cache.") # Logging
            return self.active_games[game_uuid]

        print(f"Game {game_uuid} not in cache, attempting to load from storage.") # Logging
        try:
            # Assuming load_game_state expects UUID
            game_state = state_service.load_game_state(game_uuid)
            if game_state:
                self.active_games[game_uuid] = game_state
                print(f"Game {game_uuid} loaded from storage and cached.") # Logging
                return game_state
            else:
                print(f"Game {game_uuid} not found in storage.") # Logging
                return None
        except Exception as e:
            # Log the error appropriately
            print(f"Error loading game state for game {game_uuid}: {e}")
            return None # Return None or raise an exception, depending on desired handling

    def update_game_state(self, game_id_str: str, new_state: GameState) -> bool:
        """Updates the game state in the cache and persists it to storage."""
        try:
            game_uuid = UUID(game_id_str)
        except ValueError:
             print(f"Invalid game ID format for update: {game_id_str}") # Logging
             return False

        if game_uuid != new_state.game_id:
             print(f"Error: Mismatched game_id {game_uuid} vs {new_state.game_id} in update_game_state") # Logging
             return False # Or raise ValueError

        try:
            # Assuming save_game_state expects UUID
            state_service.save_game_state(game_uuid, new_state)
            self.active_games[game_uuid] = new_state
            print(f"Game {game_uuid} updated and saved.") # Logging
            return True
        except Exception as e:
            # Log the error appropriately
            print(f"Error saving updated game state for game {game_uuid}: {e}")
            # Consider cache consistency: should we revert the cache update if save fails?
            return False

    def remove_game_from_cache(self, game_id_str: str):
         """Removes a game from the active cache (e.g., when completed or inactive)."""
         try:
            game_uuid = UUID(game_id_str)
         except ValueError:
             print(f"Invalid game ID format for cache removal: {game_id_str}") # Logging
             return # Do nothing if ID is invalid

         if game_uuid in self.active_games:
             del self.active_games[game_uuid]
             print(f"Game {game_uuid} removed from cache.") # Logging

# Optional: Instantiate a global game manager instance if desired
# game_manager = GameManager() 
game_manager = GameManager() # Make the instance available globally 
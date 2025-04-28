from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
import uuid

from app.models.game import GameState
from app.models.settings import GameSettings
from app.services.game_manager import game_manager
from app.services import state_service

router = APIRouter()

@router.post("/game", response_model=GameState, status_code=status.HTTP_201_CREATED)
async def create_new_game(
    settings: GameSettings,
    # Remove dependency injection for now
    # game_manager: GameManager = Depends(get_game_manager)
):
    """
    Creates a new game based on the provided settings.
    """
    try:
        # Use the imported global instance
        new_game_state = game_manager.create_game(settings)
        return new_game_state
    except ValueError as ve:
         # Catch potential errors from _assign_roles or settings validation
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        # TODO: More specific exception handling
        print(f"Error creating game: {e}") # Basic logging
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error creating game.")

@router.get("/game/{game_id}", response_model=GameState)
async def get_game_by_id(
    game_id: str,
    # Remove dependency injection
    # game_manager: GameManager = Depends(get_game_manager)
):
    """
    Retrieves the current state of a specific game.
    """
    # Use the imported global instance
    game_state = game_manager.get_game(game_id)

    if game_state is None:
        # Check if the ID format was invalid (get_game returns None for this)
        try:
            uuid.UUID(game_id)
            # If UUID is valid, then the game was truly not found
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Game with ID {game_id} not found")
        except ValueError:
            # If UUID is invalid
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid game ID format: {game_id}")

    # TODO: Implement filtering of sensitive info based on requesting player if needed
    return game_state

@router.get("/games", response_model=List[str])
async def list_all_games():
    """
    Retrieves a list of IDs for all saved games.
    """
    try:
        # Note: state_service functions are not async, adjust if they become async later
        saved_games_uuids = state_service.list_saved_games()
        # Convert UUIDs to strings for the response
        return [str(game_uuid) for game_uuid in saved_games_uuids]
    except Exception as e:
        # TODO: More specific exception handling
        print(f"Error listing games: {e}") # Basic logging
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error listing games.") 
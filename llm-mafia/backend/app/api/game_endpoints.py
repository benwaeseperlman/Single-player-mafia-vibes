from fastapi import APIRouter, HTTPException, Depends, status, Body
from typing import List
import uuid
from uuid import UUID # Import UUID
from datetime import datetime # Import datetime

from pydantic import BaseModel # Import BaseModel

from app.models.game import GameState, GamePhase, ChatMessage # Import GamePhase, ChatMessage
from app.models.settings import GameSettings
from app.models.player import PlayerStatus # Import PlayerStatus
from app.models.actions import ActionType # Import ActionType
from app.services.game_manager import game_manager
# Import action_service and its exception
from app.services.action_service import action_service, ActionValidationError
from app.services import state_service
# Import WebSocket Manager for broadcasting messages
from app.dependencies import get_websocket_manager
from app.services.websocket_manager import WebSocketManager

router = APIRouter()

# --- Helper Pydantic Models for Request Bodies ---

class ActionRequest(BaseModel):
    player_id: UUID
    target_id: UUID
    action_type: ActionType

class MessageRequest(BaseModel):
    player_id: UUID
    message: str

class VoteRequest(BaseModel):
    player_id: UUID # Voter
    target_id: UUID # Voted for

# --- Existing Endpoints ---

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

# --- New Endpoints for Player Actions (Step 14) ---

@router.post("/game/{game_id}/action", status_code=status.HTTP_204_NO_CONTENT)
async def submit_player_action(
    game_id: str,
    action_data: ActionRequest,
):
    """
    Submits a night action for a player (Mafia Kill, Detective Investigate, Doctor Protect).
    """
    game_state = await game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Game {game_id} not found.")

    # Validate phase (only Night actions handled here)
    if game_state.phase != GamePhase.NIGHT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Actions can only be submitted during the Night phase.")

    # Validate action type is a night action
    if action_data.action_type not in [ActionType.MAFIA_KILL, ActionType.DETECTIVE_INVESTIGATE, ActionType.DOCTOR_PROTECT]:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action type for this endpoint.")

    try:
        action_service.record_night_action(
            game_state,
            action_data.player_id,
            action_data.target_id,
            action_data.action_type
        )
        # Note: We don't broadcast night actions immediately. They are resolved at the start of Day.
        # We might need to save the state here if record_night_action doesn't persist.
        # Let's assume record_night_action modifies the state in memory, and phase logic saves it.
        # Re-saving here might be redundant or cause race conditions depending on design.
        # Let's skip saving here for now and rely on phase logic saving.
        return # Return 204 No Content on success

    except ActionValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e: # Catch player/target not found errors from action_service
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        print(f"Error submitting action for game {game_id}: {e}") # Basic logging
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error submitting action.")


@router.post("/game/{game_id}/message", status_code=status.HTTP_204_NO_CONTENT)
async def submit_player_message(
    game_id: str,
    message_data: MessageRequest,
    websocket_manager: WebSocketManager = Depends(get_websocket_manager) # Inject WebSocketManager
):
    """
    Submits a chat message from a player during the Day phase.
    """
    game_state = await game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Game {game_id} not found.")

    # Validate phase
    if game_state.phase != GamePhase.DAY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Messages can only be sent during the Day phase.")

    # Find the player submitting the message
    player = next((p for p in game_state.players if p.id == message_data.player_id), None)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Player {message_data.player_id} not found in game {game_id}.")
    if player.status != PlayerStatus.ALIVE:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dead players cannot send messages.")
    # TODO: Check if the player is human? Or allow AI messages via API too? Assuming human only for now.
    if not player.is_human:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only human players can submit messages via this endpoint.")


    try:
        # Create the chat message object
        chat_message = ChatMessage(
            player_id=message_data.player_id,
            message=message_data.message
            # timestamp is added automatically
        )

        # Append to chat history
        game_state.chat_history.append(chat_message)
        game_state.updated_at = chat_message.timestamp # Update game state timestamp

        # Update and broadcast the state change
        # GameManager's update_game_state handles saving and broadcasting
        success = await game_manager.update_game_state(game_id, game_state)
        if not success:
             # update_game_state already logged the error
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update game state with new message.")

        return # Return 204 No Content on success

    except ValueError as e: # Catches Pydantic validation errors for ChatMessage
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid message data: {e}")
    except Exception as e:
        print(f"Error submitting message for game {game_id}: {e}") # Basic logging
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error submitting message.")


@router.post("/game/{game_id}/vote", status_code=status.HTTP_204_NO_CONTENT)
async def submit_player_vote(
    game_id: str,
    vote_data: VoteRequest,
):
    """
    Submits a player's vote during the Voting phase.
    """
    game_state = await game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Game {game_id} not found.")

    # Validate phase
    if game_state.phase != GamePhase.VOTING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Votes can only be submitted during the Voting phase.")

    # Find the voter and target players
    voter = next((p for p in game_state.players if p.id == vote_data.player_id), None)
    target = next((p for p in game_state.players if p.id == vote_data.target_id), None)

    if not voter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Voter player {vote_data.player_id} not found.")
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target player {vote_data.target_id} not found.")

    # Validate players are alive
    if voter.status != PlayerStatus.ALIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dead players cannot vote.")
    if target.status != PlayerStatus.ALIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot vote for a dead player.")
        
    # TODO: Check if the player is human? Or allow AI votes via API too? Assuming human only for now.
    if not voter.is_human:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only human players can submit votes via this endpoint.")


    try:
        # Record the vote (overwriting previous vote if any)
        # Store voter ID as string key and target ID as string value for consistency
        game_state.votes[str(voter.id)] = str(target.id)
        game_state.updated_at = datetime.now() # Update timestamp

        # Update and broadcast the state change
        success = await game_manager.update_game_state(game_id, game_state)
        if not success:
             # update_game_state already logged the error
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update game state with new vote.")

        return # Return 204 No Content on success

    except Exception as e:
        print(f"Error submitting vote for game {game_id}: {e}") # Basic logging
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error submitting vote.") 
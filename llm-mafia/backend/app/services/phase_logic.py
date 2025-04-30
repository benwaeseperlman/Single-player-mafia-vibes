from typing import Dict, List, Optional, Tuple, Union
from uuid import UUID
import random
import logging # Added logging

from app.models.game import GamePhase, GameState
from app.models.player import Player, PlayerStatus, Role
# Import action models when they are defined (Step 8)
# from app.models.actions import MafiaTarget, DetectiveInvestigation, DoctorProtection, Vote

# Import state service for persistence (already implemented)
from .state_service import save_game_state
# Import action service when available (Step 8)
from .action_service import action_service, ActionValidationError
# Import LLM Service (Step 10)
from .llm_service import llm_service, LLMServiceError

# Import action models
from app.models.actions import (
    ActionType,
    BaseAction,
    MafiaKillAction,
    DetectiveInvestigateAction,
    DoctorProtectAction,
    ChatMessage
)

# Setup logger
logger = logging.getLogger(__name__)


def _check_win_condition(game_state: GameState) -> Optional[GamePhase]:
    """Checks if a win condition has been met.

    Returns:
        GamePhase.GAMEOVER if a faction has won, otherwise None.
    """
    living_players = [p for p in game_state.players if p.status == PlayerStatus.ALIVE]
    mafia_count = sum(1 for p in living_players if p.role == Role.MAFIA)
    innocent_count = len(living_players) - mafia_count

    if mafia_count == 0:
        game_state.add_to_history("Game Over: All Mafia have been eliminated. Innocents win!")
        game_state.winner = "innocents"
        return GamePhase.GAMEOVER
    if mafia_count >= innocent_count:
        game_state.add_to_history("Game Over: Mafia outnumber or equal Innocents. Mafia win!")
        game_state.winner = "mafia"
        return GamePhase.GAMEOVER

    return None

def _resolve_night_actions(game_state: GameState) -> Tuple[Optional[Player], Optional[Player], List[str]]:
    """
    Processes stored night actions to determine kills, saves, and investigation results.

    This function retrieves actions recorded in `game_state.night_actions`, determines
    the outcome based on Mafia kill attempts and Doctor saves, updates player statuses,
    and prepares announcements for the Day phase. It also stores Detective investigation
    results privately on the Detective's player object.

    Returns:
        Tuple: (killed_player, saved_player, announcement_strings)
    """
    killed_player: Optional[Player] = None
    saved_player: Optional[Player] = None
    detective_result: Optional[str] = None # Stored privately, not announced publicly
    announcements: List[str] = []

    # Helper to find player by ID
    def get_player(player_id: UUID) -> Optional[Player]:
        return next((p for p in game_state.players if p.id == player_id), None)

    # Identify actions by type
    mafia_action: Optional[MafiaKillAction] = None
    doctor_action: Optional[DoctorProtectAction] = None
    detective_action: Optional[DetectiveInvestigateAction] = None

    for action_key, action_value in game_state.night_actions.items():
        # Check type based on the action model stored
        if isinstance(action_value, MafiaKillAction):
            # Assumes a single Mafia kill action is stored using ActionType.MAFIA_KILL as key
            mafia_action = action_value
        elif isinstance(action_value, DoctorProtectAction):
            doctor_action = action_value
        elif isinstance(action_value, DetectiveInvestigateAction):
            detective_action = action_value

    # Determine who was saved
    doctor_save_target_id: Optional[UUID] = None
    if doctor_action:
        saved_player = get_player(doctor_action.target_id)
        if saved_player and saved_player.status == PlayerStatus.ALIVE:
            doctor_save_target_id = saved_player.id
            saved_player.is_saved = True # Mark player as saved for this night potentially
            # Note: saved_player object is updated, but status change depends on Mafia action
            game_state.add_to_history(f"Doctor chose to protect {saved_player.name}.") # Log internal choice

    # Determine Mafia Kill outcome
    if mafia_action:
        mafia_target = get_player(mafia_action.target_id)
        if mafia_target and mafia_target.status == PlayerStatus.ALIVE:
            if mafia_target.id == doctor_save_target_id:
                # Player was saved!
                announcement = (f"Night fell, and while danger lurked, "
                                f"{mafia_target.name} (ID: {mafia_target.id}) survived the attack thanks to protection!")
                announcements.append(announcement)
                game_state.add_to_history(announcement)
                # saved_player is already set above
            else:
                # Player was killed
                killed_player = mafia_target
                killed_player.status = PlayerStatus.DEAD
                announcement = (f"Night fell, and tragedy struck. {killed_player.name} (ID: {killed_player.id}) "
                                f"was killed. They were a {killed_player.role.value}.")
                announcements.append(announcement)
                game_state.add_to_history(announcement)
                # Ensure saved_player is None if the killed player wasn't the one saved
                if saved_player and saved_player.id != doctor_save_target_id:
                    saved_player.is_saved = False # Unmark if they weren't the target
                    saved_player = None # Reset saved_player if it wasn't the target

        elif mafia_target and mafia_target.status == PlayerStatus.DEAD:
             # Mafia targeted an already dead player
             announcement = "The night passed uneventfully. The intended target was already deceased."
             announcements.append(announcement)
             game_state.add_to_history(announcement)
             if saved_player: # Clear save status if target was dead
                 saved_player.is_saved = False
                 saved_player = None

    # If no Mafia action occurred (e.g., only one Mafia died night before)
    if not mafia_action and not killed_player:
        announcement = "The night passed peacefully. No one was killed."
        announcements.append(announcement)
        game_state.add_to_history(announcement)
        if saved_player: # Still note the save even if no attack
             saved_player.is_saved = True # Keep marked as saved for this night

    # Process Detective Investigation (Store result privately)
    if detective_action:
        detective = get_player(detective_action.player_id)
        investigation_target = get_player(detective_action.target_id)
        if detective and investigation_target and detective.status == PlayerStatus.ALIVE:
            target_is_mafia = investigation_target.role == Role.MAFIA
            result_text = "Mafia" if target_is_mafia else "Innocent"
            detective.investigation_result = f"Your investigation of {investigation_target.name} revealed they are {result_text}."
            # History log for debugging/internal tracking - NOT public announcement
            game_state.add_to_history(f"Detective investigated {investigation_target.name}, result: {result_text}.")

    # Clear actions and save status for the next night
    game_state.night_actions = {}
    for p in game_state.players:
        p.is_saved = False # Reset save status for all players
        # Keep investigation result until next investigation or game end

    return killed_player, saved_player, announcements


def advance_to_night(game_state: GameState, game_id: str) -> GameState:
    """Advances the game state to the Night phase and triggers AI night actions."""
    if game_state.phase == GamePhase.DAY or game_state.phase == GamePhase.VOTING:
        game_state.day_number += 1 # Increment day number when moving from Day/Voting to Night

    game_state.phase = GamePhase.NIGHT
    game_state.add_to_history(f"Night falls. Day {game_state.day_number}.")
    # Reset pending actions/votes for the new phase
    game_state.night_actions = {}
    game_state.votes = {}

    # Immediately save state after phase change, before AI actions
    save_game_state(game_id, game_state) 

    # Trigger AI Night Actions (Step 10)
    for player in game_state.players:
        if not player.is_human and player.status == PlayerStatus.ALIVE and player.role in [Role.MAFIA, Role.DOCTOR, Role.DETECTIVE]:
            try:
                ai_action = llm_service.determine_ai_night_action(player, game_state)
                if ai_action:
                    try:
                        # Use action_service to record the action, which updates game_state.night_actions
                        action_service.record_night_action(game_state, ai_action)
                        game_state.add_to_history(f"AI {player.role.value} ({player.id}) has decided their action.") # Log internal decision
                        # NOTE: Do not save state after every single AI action. Save once after all AI actions or rely on next phase transition save.
                    except ActionValidationError as ave:
                        game_state.add_to_history(f"AI {player.role.value} ({player.id}) failed to record action: {ave}")
                        # logger.warning(f"Validation Error for AI {player.id}: {ave}") # Log error using logger
                        print(f"Validation Error for AI {player.id}: {ave}")
            except LLMServiceError as llme:
                game_state.add_to_history(f"AI {player.role.value} ({player.id}) failed to determine action due to LLM error: {llme}")
                # logger.error(f"LLM Service Error for AI {player.id}: {llme}") # Log error using logger
                print(f"LLM Service Error for AI {player.id}: {llme}")
            except Exception as e:
                game_state.add_to_history(f"Unexpected error determining action for AI {player.role.value} ({player.id}): {e}")
                # logger.exception(f"Unexpected Error for AI {player.id}") # Log error with stack trace
                print(f"Unexpected Error for AI {player.id}: {e}")

    # Save state again *after* all potential AI actions are recorded
    save_game_state(game_id, game_state)

    # Trigger WebSocket update (Step 13)
    return game_state


def advance_to_day(game_state: GameState, game_id: str) -> GameState:
    """
    Processes night actions, updates status, checks win conditions, and advances to Day phase.
    """
    if game_state.phase != GamePhase.NIGHT:
        return game_state

    # 1. Process Night Actions (updates status and adds announcements to history directly)
    killed_player, saved_player, announcements = _resolve_night_actions(game_state)
    # Note: Announcements are now strings derived from the logic above.

    # 2. Check Win Conditions (updates history and winner status if game over)
    win_condition = _check_win_condition(game_state)
    if win_condition:
        game_state.phase = win_condition
        save_game_state(game_id, game_state)
        # Trigger WebSocket update (Step 13)
        return game_state

    # 3. Update Phase
    game_state.phase = GamePhase.DAY
    game_state.add_to_history(f"Day {game_state.day_number}. Discuss and decide who to lynch.")
    save_game_state(game_id, game_state)

    # 4. Trigger AI Discussion (Step 11)
    ai_messages: List[ChatMessage] = []
    for player in game_state.players:
        if not player.is_human and player.status == PlayerStatus.ALIVE:
            try:
                ai_message = llm_service.generate_ai_day_message(player, game_state)
                if ai_message:
                    ai_messages.append(ai_message)
                    # Optionally add to history immediately, or just collect
                    # game_state.add_to_history(f"AI {player.name} ({player.id}) says: {ai_message.message}") 
            except LLMServiceError as llme:
                game_state.add_to_history(f"AI {player.name} ({player.id}) failed to generate message due to LLM error: {llme}")
                # logger.error(f"LLM Service Error for AI {player.id} Day Msg: {llme}") # Log error
                print(f"LLM Service Error for AI {player.id} Day Msg: {llme}")
            except Exception as e:
                game_state.add_to_history(f"Unexpected error generating message for AI {player.name} ({player.id}): {e}")
                # logger.exception(f"Unexpected Error for AI {player.id} Day Msg") # Log error with stack trace
                print(f"Unexpected Error for AI {player.id} Day Msg: {e}")
                
    # Add all generated AI messages to chat history
    # Consider randomizing order later if needed
    if ai_messages:
        game_state.chat_history.extend(ai_messages)
        # Maybe save state again after adding messages?
        save_game_state(game_id, game_state) 
        
    # 5. Trigger WebSocket update (Step 13) with phase change and potentially announcements

    return game_state


def advance_to_voting(game_state: GameState, game_id: str) -> GameState:
    """Advances the game state to the Voting phase and triggers AI voting."""
    if game_state.phase != GamePhase.DAY:
        return game_state

    game_state.phase = GamePhase.VOTING
    game_state.add_to_history("Voting has begun! Choose who to lynch.")
    # Clear previous votes
    game_state.votes = {}
    
    # Immediately save state after phase change, before AI actions
    save_game_state(game_id, game_state) 

    # Trigger AI Voting (Step 12)
    for player in game_state.players:
         if not player.is_human and player.status == PlayerStatus.ALIVE:
            try:
                voted_player_id = llm_service.determine_ai_vote(player, game_state)
                if voted_player_id:
                    # Directly record the vote in the game state
                    # Validation of voted_player_id happens within llm_service
                    game_state.votes[player.id] = voted_player_id
                    game_state.add_to_history(f"AI {player.name} ({player.id}) has cast their vote.") # Log internal action
                else:
                     game_state.add_to_history(f"AI {player.name} ({player.id}) could not determine a vote.")
                     # logger.warning(f"AI Player {player.id} did not return a vote.")
                     print(f"AI Player {player.id} did not return a vote.")

            except LLMServiceError as llme:
                game_state.add_to_history(f"AI {player.name} ({player.id}) failed to vote due to LLM error: {llme}")
                # logger.error(f"LLM Service Error for AI {player.id} vote: {llme}")
                print(f"LLM Service Error for AI {player.id} vote: {llme}")
            except Exception as e:
                game_state.add_to_history(f"Unexpected error determining vote for AI {player.name} ({player.id}): {e}")
                # logger.exception(f"Unexpected Error for AI {player.id} vote")
                print(f"Unexpected Error for AI {player.id} vote: {e}")

    # Save state again *after* all potential AI votes are recorded
    save_game_state(game_id, game_state)

    # Trigger WebSocket update (Step 13)
    return game_state


def process_voting_and_advance(game_state: GameState, game_id: str, votes: Dict[UUID, UUID]) -> GameState:
    """Processes votes, handles lynching/ties, checks win conditions, and advances phase.
    
    Accepts votes dictionary directly for now. In the future, this might just use game_state.votes.
    For now, it assumes the input `votes` combines human and AI votes.
    """
    if game_state.phase != GamePhase.VOTING:
        return game_state # Or raise error
    
    # Use the votes passed in (or merge with game_state.votes if needed later)
    current_votes = votes
    # TODO: Refine how votes are collected (e.g., maybe game_state.votes is the single source)
    game_state.votes = current_votes # Overwrite state votes with the processed ones for history/consistency

    if not current_votes:
        game_state.add_to_history("No votes were cast. Proceeding to night.")
        return advance_to_night(game_state, game_id)

    # Tally votes
    vote_counts = {}
    for voter_id, target_id in current_votes.items():
        vote_counts[target_id] = vote_counts.get(target_id, 0) + 1

    # Determine highest vote count
    max_votes = 0
    lynched_player_id = None
    tie = False
    if vote_counts:
        sorted_votes = sorted(vote_counts.items(), key=lambda item: item[1], reverse=True)
        max_votes = sorted_votes[0][1]
        top_voted_ids = [pid for pid, count in sorted_votes if count == max_votes]
        
        if len(top_voted_ids) == 1:
            lynched_player_id = top_voted_ids[0]
            tie = False
        else:
            tie = True

    # Handle outcome
    if tie:
        game_state.add_to_history(f"Voting resulted in a tie with {max_votes} votes each. No one is lynched.")
        # Optionally implement tie-breaking logic here
        # Advance to Night
        return advance_to_night(game_state, game_id)
    elif lynched_player_id:
        lynched_player = next((p for p in game_state.players if p.id == lynched_player_id), None)
        if lynched_player:
            lynched_player.status = PlayerStatus.DEAD
            game_state.add_to_history(f"{lynched_player.name} (ID: {lynched_player.id}) has been lynched with {max_votes} votes. They were a {lynched_player.role.value}.")
            # Check win condition after lynching
            win_condition = _check_win_condition(game_state)
            if win_condition:
                game_state.phase = win_condition
                save_game_state(game_id, game_state)
                return game_state
            else:
                # Advance to Night
                return advance_to_night(game_state, game_id)
        else:
             game_state.add_to_history(f"Error: Lynched player ID {lynched_player_id} not found. Proceeding to night.")
             return advance_to_night(game_state, game_id)
    else:
         # Should not happen if votes were cast, but handle defensively
         game_state.add_to_history("Voting concluded with no one lynched. Proceeding to night.")
         return advance_to_night(game_state, game_id)

    # Fallback save just in case (though transitions should handle it)
    save_game_state(game_id, game_state)
    return game_state 
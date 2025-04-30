from typing import Dict, List, Optional, Tuple, Union
from uuid import UUID
import random
import logging # Added logging
import asyncio # Add asyncio import

from app.models.game import GamePhase, GameState
from app.models.player import Player, PlayerStatus, Role
# Import action models when they are defined (Step 8)
# from app.models.actions import MafiaTarget, DetectiveInvestigation, DoctorProtection, Vote

# Import state service for persistence (already implemented)
# from .state_service import save_game_state # No longer directly used here
# Import the global game manager instance
from .game_manager import game_manager
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


async def advance_to_night(game_state: GameState, game_id: str) -> GameState:
    """Advances the game state to the Night phase and triggers AI night actions."""
    if game_state.phase == GamePhase.DAY or game_state.phase == GamePhase.VOTING:
        game_state.day_number += 1 # Increment day number when moving from Day/Voting to Night

    game_state.phase = GamePhase.NIGHT
    game_state.add_to_history(f"Night falls. Day {game_state.day_number}.")
    # Reset pending actions/votes for the new phase
    game_state.night_actions = {}
    game_state.votes = {}

    # Immediately save state after phase change, before AI actions
    # save_game_state(game_id, game_state)
    await game_manager.update_game_state(game_id, game_state) # Save and broadcast

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
    # save_game_state(game_id, game_state)
    await game_manager.update_game_state(game_id, game_state) # Save and broadcast final night state

    # Trigger WebSocket update (Step 13) - Handled by update_game_state
    return game_state


async def advance_to_day(game_state: GameState, game_id: str) -> GameState:
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
        # save_game_state(game_id, game_state)
        await game_manager.update_game_state(game_id, game_state) # Save and broadcast game over state
        # Trigger WebSocket update (Step 13) - Handled by update_game_state
        return game_state

    # 3. Update Phase
    game_state.phase = GamePhase.DAY
    game_state.add_to_history(f"Day {game_state.day_number}. Discuss and decide who to lynch.")
    # save_game_state(game_id, game_state)
    await game_manager.update_game_state(game_id, game_state) # Save and broadcast start of day state

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
        # Save and broadcast state *after* AI messages are added
        await game_manager.update_game_state(game_id, game_state)

    # Trigger WebSocket update (Step 13) - Handled by update_game_state calls above
    return game_state


async def advance_to_voting(game_state: GameState, game_id: str) -> GameState:
    """
    Advances the game state to the Voting phase.
    """
    if game_state.phase != GamePhase.DAY:
        return game_state

    game_state.phase = GamePhase.VOTING
    game_state.votes = {} # Clear previous votes
    game_state.add_to_history("Voting phase begins. Please cast your votes.")
    # save_game_state(game_id, game_state)
    await game_manager.update_game_state(game_id, game_state) # Save and broadcast voting phase start

    # Trigger AI Voting (Step 12)
    ai_votes: Dict[UUID, UUID] = {}
    for player in game_state.players:
        if not player.is_human and player.status == PlayerStatus.ALIVE:
            try:
                target_id = llm_service.determine_ai_vote(player, game_state)
                if target_id:
                    ai_votes[player.id] = target_id # Use UUID for player ID key
                    # Optional: Log AI vote choice internally
                    game_state.add_to_history(f"AI {player.name} ({player.id}) has decided their vote.")
                else:
                    game_state.add_to_history(f"AI {player.name} ({player.id}) abstained or failed to vote.")
            except LLMServiceError as llme:
                game_state.add_to_history(f"AI {player.name} ({player.id}) failed to determine vote due to LLM error: {llme}")
                # logger.error(f"LLM Service Error for AI {player.id} Vote: {llme}") # Log error
                print(f"LLM Service Error for AI {player.id} Vote: {llme}")
            except Exception as e:
                game_state.add_to_history(f"Unexpected error determining vote for AI {player.name} ({player.id}): {e}")
                # logger.exception(f"Unexpected Error for AI {player.id} Vote") # Log error with stack trace
                print(f"Unexpected Error for AI {player.id} Vote: {e}")

    # Add AI votes to the game state
    if ai_votes:
        game_state.votes.update(ai_votes)
        # Save and broadcast state *after* AI votes are added
        await game_manager.update_game_state(game_id, game_state)

    # Trigger WebSocket update (Step 13) - Handled by update_game_state calls
    return game_state


async def process_voting_and_advance(game_state: GameState, game_id: str, votes: Dict[UUID, UUID]) -> GameState:
    """Processes votes, handles lynching, checks win conditions, and advances phase."""
    if game_state.phase != GamePhase.VOTING:
        return game_state

    # Update game state with the received votes (primarily human vote if applicable, AI votes already in)
    # This assumes 'votes' dict might contain the human vote
    # If human vote comes via a separate mechanism, adjust logic here
    game_state.votes.update(votes) # Merge in any new votes (e.g., human vote)
    # Save state with all votes recorded *before* processing
    await game_manager.update_game_state(game_id, game_state)

    # Tally Votes
    vote_counts: Dict[UUID, int] = {}
    valid_voters = {p.id for p in game_state.players if p.status == PlayerStatus.ALIVE}
    living_player_ids = {p.id for p in game_state.players if p.status == PlayerStatus.ALIVE}

    for voter_id, target_id in game_state.votes.items():
        # Ensure voter is alive and target is valid (and alive)
        if voter_id in valid_voters and target_id in living_player_ids:
            vote_counts[target_id] = vote_counts.get(target_id, 0) + 1
            # Log individual votes for history/transparency
            voter_name = next((p.name for p in game_state.players if p.id == voter_id), "Unknown")
            target_name = next((p.name for p in game_state.players if p.id == target_id), "Unknown")
            game_state.add_to_history(f"{voter_name} voted for {target_name}.")
        elif voter_id in valid_voters:
             voter_name = next((p.name for p in game_state.players if p.id == voter_id), "Unknown")
             game_state.add_to_history(f"{voter_name}'s vote for {target_id} was invalid (target not alive or invalid ID). ")

    # Determine Lynched Player
    lynched_player: Optional[Player] = None
    if vote_counts:
        max_votes = max(vote_counts.values())
        potential_lynches = [pid for pid, count in vote_counts.items() if count == max_votes]

        if len(potential_lynches) == 1:
            # Clear winner
            lynched_player_id = potential_lynches[0]
            lynched_player = next((p for p in game_state.players if p.id == lynched_player_id), None)
            if lynched_player:
                lynched_player.status = PlayerStatus.DEAD
                game_state.add_to_history(
                    f"The town has voted. {lynched_player.name} (ID: {lynched_player.id}) has been lynched. "
                    f"They were a {lynched_player.role.value}."
                )
            else:
                # Should not happen if IDs are consistent
                game_state.add_to_history("Error: Lynched player ID not found.")
        else:
            # Tie
            tied_names = [next((p.name for p in game_state.players if p.id == pid), "Unknown") for pid in potential_lynches]
            game_state.add_to_history(f"Voting resulted in a tie between: {', '.join(tied_names)}. No one is lynched.")
    else:
        game_state.add_to_history("No valid votes were cast. No one is lynched.")

    # Check Win Conditions again after lynching
    win_condition = _check_win_condition(game_state)
    if win_condition:
        game_state.phase = win_condition
        await game_manager.update_game_state(game_id, game_state) # Save and broadcast final state
        return game_state

    # Advance to the next phase (Night)
    # The advance_to_night function handles setting the phase, saving, and broadcasting
    # No need to call update_game_state here, advance_to_night will do it.
    # return advance_to_night(game_state, game_id)
    # Call the async version
    return await advance_to_night(game_state, game_id) 
from typing import Dict, List, Optional, Tuple, Union
from uuid import UUID
import random

from app.models.game import GamePhase, GameState
from app.models.player import Player, PlayerStatus, Role
# Import action models when they are defined (Step 8)
# from app.models.actions import MafiaTarget, DetectiveInvestigation, DoctorProtection, Vote

# Import state service for persistence (already implemented)
from .state_service import save_game_state
# Import action service when available (Step 8)
# from .action_service import get_pending_actions, clear_pending_actions

# Import action models
from app.models.actions import (
    ActionType,
    BaseAction,
    MafiaKillAction,
    DetectiveInvestigateAction,
    DoctorProtectAction,
)


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
    """Advances the game state to the Night phase."""
    if game_state.phase == GamePhase.DAY or game_state.phase == GamePhase.VOTING:
        game_state.day_number += 1 # Increment day number when moving from Day/Voting to Night

    game_state.phase = GamePhase.NIGHT
    game_state.add_to_history(f"Night falls. Day {game_state.day_number}.")
    # Reset pending actions/votes for the new phase (replace with service calls later)
    game_state.night_actions = {}
    game_state.votes = {}

    save_game_state(game_id, game_state)
    # Trigger LLM Night Actions (Step 10)
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
    # 5. Trigger WebSocket update (Step 13) with phase change and potentially announcements

    return game_state


def advance_to_voting(game_state: GameState, game_id: str) -> GameState:
    """Advances the game state from Day discussion to Voting phase."""
    if game_state.phase != GamePhase.DAY:
        return game_state

    game_state.phase = GamePhase.VOTING
    game_state.add_to_history("Discussion ended. Time to vote.")
    game_state.votes = {} # Clear pending votes for the new voting round
    save_game_state(game_id, game_state)
    # Trigger LLM Voting (Step 12)
    # Trigger WebSocket update (Step 13)
    return game_state


def process_voting_and_advance(game_state: GameState, game_id: str, votes: Dict[str, str]) -> GameState:
    """
    Tallies votes, determines lynched player, updates status, checks win conditions,
    and advances to Night or GameOver.
    NOTE: votes Dict format: {voter_id: target_id}
    """
    if game_state.phase != GamePhase.VOTING:
        return game_state

    # 1. Tally Votes
    vote_counts: Dict[str, int] = {}
    # Use string IDs as stored in GameState model
    living_player_ids = {str(p.id) for p in game_state.players if p.status == PlayerStatus.ALIVE}

    for voter_id, target_id in votes.items():
        # Ensure only living players' votes are counted and they vote for living players
        if str(voter_id) in living_player_ids and str(target_id) in living_player_ids:
            vote_counts[str(target_id)] = vote_counts.get(str(target_id), 0) + 1

    lynched_player_id_str: Optional[str] = None
    if vote_counts:
        max_votes = max(vote_counts.values())
        candidates = [p_id for p_id, count in vote_counts.items() if count == max_votes]
        if len(candidates) == 1:
            lynched_player_id_str = candidates[0]

    # 2. Process Lynch Result
    if lynched_player_id_str:
        lynched_player = next((p for p in game_state.players if str(p.id) == lynched_player_id_str), None)
        if lynched_player:
            lynched_player.status = PlayerStatus.DEAD # Update status directly
            announcement = f"{lynched_player.name} (ID: {lynched_player.id}) was lynched. They were a {lynched_player.role.value}."
            game_state.add_to_history(announcement)
        else:
             game_state.add_to_history("Error: Lynched player ID not found.") # Should not happen
    else:
        announcement = "The vote resulted in a tie or no votes were cast. No one was lynched."
        game_state.add_to_history(announcement)

    # 3. Check Win Conditions (updates history and winner status if game over)
    win_condition = _check_win_condition(game_state)
    if win_condition:
        game_state.phase = win_condition
        save_game_state(game_id, game_state)
        # Trigger WebSocket update (Step 13)
        return game_state

    # 4. Advance to Next Phase (Night)
    # Save before advancing to capture the state after vote processing but before night starts
    save_game_state(game_id, game_state)
    return advance_to_night(game_state, game_id) 
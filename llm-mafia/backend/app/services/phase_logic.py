from typing import Dict, List, Optional, Tuple
import random

from app.models.game import GamePhase, GameState
from app.models.player import Player, PlayerStatus, Role
# Import action models when they are defined (Step 8)
# from app.models.actions import MafiaTarget, DetectiveInvestigation, DoctorProtection, Vote

# Import state service for persistence (already implemented)
from .state_service import save_game_state
# Import action service when available (Step 8)
# from .action_service import get_pending_actions, clear_pending_actions


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
    NOTE: This is a placeholder implementation. Full logic depends on Step 8 (Action Service).
    For now, it assumes mock actions might be stored directly in game_state or returns defaults.

    Returns:
        Tuple: (killed_player, saved_player, announcement_strings)
    """
    # Placeholder logic - replace with actual action retrieval and processing from action_service
    killed_player: Optional[Player] = None
    saved_player: Optional[Player] = None
    announcements: List[str] = []

    # --- Placeholder Action Processing ---
    # In a real implementation (Step 8+), we'd fetch actions:
    # actions = get_pending_actions(game_state.game_id)
    # ... process actions ...

    # Mock: Randomly decide if someone is killed for testing phase flow
    living_players = [p for p in game_state.players if p.status == PlayerStatus.ALIVE and p.role != Role.MAFIA] # Mafia can't kill each other
    # Simulate someone being saved by ensuring they are not a potential target
    # In a real implementation, this would use the actual doctor_save_id from actions
    mock_saved_player_id: Optional[UUID] = None
    doctor = next((p for p in game_state.players if p.role == Role.DOCTOR and p.status == PlayerStatus.ALIVE), None)
    if doctor: # Simulate doctor saving someone randomly for placeholder
        save_targets = [p.id for p in game_state.players if p.status == PlayerStatus.ALIVE]
        if save_targets:
             mock_saved_player_id = random.choice(save_targets)

    potential_targets = [p for p in living_players if p.id != mock_saved_player_id]

    if potential_targets and random.choice([True, False]): # 50% chance of kill
        killed_player = random.choice(potential_targets)
        killed_player.status = PlayerStatus.DEAD # Update status directly
        announcement = f"Night fell, and tragedy struck. {killed_player.name} (ID: {killed_player.id}) was killed. They were a {killed_player.role.value}."
        announcements.append(announcement)
        # Also add directly to history for persistence, mirroring the announcement
        game_state.add_to_history(announcement)

    # Placeholder for detective result (should be private message via WebSocket in future)
    # if detective_investigation_id: ...

    if not killed_player:
        announcement = "The night passed peacefully. No one was killed."
        announcements.append(announcement)
        # Also add directly to history
        game_state.add_to_history(announcement)

    # Clear actions after processing (Step 8)
    # clear_pending_actions(game_state.game_id)

    # Find the actual saved player object if an ID was chosen
    saved_player = next((p for p in game_state.players if p.id == mock_saved_player_id), None)

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
    # Announcements are now just strings and already added to history within _resolve_night_actions

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
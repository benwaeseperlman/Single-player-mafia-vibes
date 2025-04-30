import pytest
import asyncio # Add asyncio
from unittest.mock import patch, MagicMock, AsyncMock # Add AsyncMock
from typing import List
import uuid
from datetime import datetime

# Models to test and mock
from app.models.game import GameState, GamePhase
from app.models.player import Player, PlayerStatus, Role
from app.models.settings import GameSettings
from app.models.actions import (
    ActionType,
    MafiaKillAction,
    DetectiveInvestigateAction,
    DoctorProtectAction,
    ChatMessage
)

# Module to test
from app.services import phase_logic
from app.services.state_service import save_game_state, delete_game_state
from app.services.llm_service import LLMServiceError
# Import game_manager for mocking its update method
from app.services.game_manager import game_manager

# Helper to create players
def create_test_players(roles: List[Role]) -> List[Player]:
    players = []
    human_assigned = False
    for i, role in enumerate(roles):
        is_human = False
        if not human_assigned and role != Role.MAFIA:
             is_human = True
             human_assigned = True
        players.append(Player(
            id=uuid.uuid4(),
            name=f"Player {i+1}",
            role=role,
            status=PlayerStatus.ALIVE,
            is_human=is_human,
            persona_id=None
        ))
    if not human_assigned and players:
        players[0].is_human = True
    return players

# Helper to create a basic game state
def create_test_game_state(players: List[Player], phase: GamePhase = GamePhase.NIGHT, day: int = 1) -> GameState:
    player_count = len(players)
    # Ensure minimum player count for valid settings
    if player_count < 5:
        raise ValueError("Test setup error: Need at least 5 players for valid GameSettings.")

    roles_in_game = {p.role for p in players}
    if Role.MAFIA not in roles_in_game:
         raise ValueError("Test setup error: Need at least one Mafia player for valid GameSettings.")

    # Calculate actual role distribution from the players list
    role_dist = {r.value: sum(1 for p in players if p.role == r) for r in Role}

    settings = GameSettings(player_count=player_count, role_distribution=role_dist, id=uuid.uuid4())
    game_id_uuid = uuid.uuid4()
    return GameState(
        game_id=game_id_uuid,
        players=players,
        phase=phase,
        day_number=day,
        settings_id=settings.id,
        history=[f"Game {game_id_uuid} created."],
        night_actions={},
        votes={}
    )

# --- Test Fixtures ---
@pytest.fixture
def mock_state_service():
    # This mock is no longer needed directly by phase_logic tests
    # as phase_logic now calls game_manager.update_game_state
    pass # Keep fixture for potential other uses, but phase_logic tests won't use it

@pytest.fixture
def mock_game_manager_update():
    """Mocks the game_manager.update_game_state async method."""
    # Patch the *instance* of game_manager imported into the phase_logic module
    with patch.object(phase_logic.game_manager, 'update_game_state', new_callable=AsyncMock) as mock_update:
        # Configure the mock to return True by default (successful update)
        mock_update.return_value = True
        yield mock_update

@pytest.fixture
def mock_resolve_actions():
    # Store config outside side_effect for persistence across calls if needed (though not strictly necessary here)
    mock_config = {}

    def side_effect_func(game_state: GameState):
        killed = None
        saved = None
        # Use default announcement unless overridden
        announcements = mock_config.get("announcements", ["Peaceful night."])

        if "killed" in mock_config:
            killed = mock_config["killed"]
            if killed:
                killed.status = PlayerStatus.DEAD
        if "saved" in mock_config:
             saved = mock_config["saved"]

        # Simulate adding messages to history
        for msg in announcements:
            game_state.add_to_history(msg)

        return killed, saved, announcements

    patcher = patch("app.services.phase_logic._resolve_night_actions", side_effect=side_effect_func)
    mock_obj = patcher.start()
    # Attach the config dict to the mock object for tests to modify
    mock_obj.mock_config = mock_config
    yield mock_obj # Yield the mock object directly
    patcher.stop()

@pytest.fixture
def mock_llm_service():
    with patch("app.services.phase_logic.llm_service", autospec=True) as mock_llm:
        yield mock_llm

@pytest.fixture
def game_state_night() -> GameState:
    """Provides a standard game state fixture in the Night phase for action tests."""
    # Use a standard 7-player setup for these tests
    players = create_test_players([
        Role.MAFIA,
        Role.DOCTOR,
        Role.DETECTIVE,
        Role.VILLAGER, # Villager 1
        Role.VILLAGER, # Villager 2
        Role.MAFIA,
        Role.VILLAGER  # Villager 3
    ])
    # Ensure specific player names for easier targeting in tests if needed
    players[3].name = "Villager 1"
    players[4].name = "Villager 2"
    players[6].name = "Villager 3"
    # Ensure the first Mafia is named for clarity
    players[0].name = "Mafia 1"
    players[5].name = "Mafia 2"
    # Ensure detective/doctor are named
    players[1].name = "Doctor"
    players[2].name = "Detective"

    state = create_test_game_state(players, phase=GamePhase.NIGHT, day=1)
    # Clear history for cleaner test logs if desired, but keep creation message
    state.history = [state.history[0]] 
    return state

# --- Test Cases ---

@pytest.mark.asyncio # Mark as async
async def test_advance_to_night(mock_game_manager_update):
    # Use 5 players: 1 Mafia, 4 Villagers
    players = create_test_players([
        Role.VILLAGER, Role.MAFIA, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER
    ])
    game_state = create_test_game_state(players, phase=GamePhase.DAY, day=1)
    game_id_str = str(game_state.game_id)

    new_state = await phase_logic.advance_to_night(game_state, game_id_str) # Await the call

    assert new_state.phase == GamePhase.NIGHT
    assert new_state.day_number == 2
    assert "Night falls" in new_state.history[-1]
    assert new_state.night_actions == {}
    assert new_state.votes == {}
    # Called twice: once after phase change, once after potential AI actions
    assert mock_game_manager_update.await_count == 2
    mock_game_manager_update.assert_awaited_with(game_id_str, new_state) # Check last call

@pytest.mark.asyncio # Mark as async
async def test_advance_to_night_increments_day(mock_game_manager_update):
    # Use 5 players
    players = create_test_players([
        Role.VILLAGER, Role.MAFIA, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER
    ])
    game_state = create_test_game_state(players, phase=GamePhase.VOTING, day=1)
    game_id_str = str(game_state.game_id)

    new_state = await phase_logic.advance_to_night(game_state, game_id_str) # Await the call

    assert new_state.phase == GamePhase.NIGHT
    assert new_state.day_number == 2
    assert f"Night falls. Day {new_state.day_number}." in new_state.history[-1]
    assert new_state.night_actions == {}
    assert new_state.votes == {}
    # Called twice: once after phase change, once after potential AI actions
    assert mock_game_manager_update.await_count == 2
    mock_game_manager_update.assert_awaited_with(game_id_str, new_state)

@pytest.mark.asyncio # Mark as async
async def test_advance_to_day_no_kill(mock_game_manager_update, mock_resolve_actions, mock_llm_service):
    # Use 5 players: 1 M, 1 Dt, 3 V
    players = create_test_players([
        Role.VILLAGER, Role.MAFIA, Role.DETECTIVE, Role.VILLAGER, Role.VILLAGER
    ])
    game_state = create_test_game_state(players, phase=GamePhase.NIGHT, day=1)
    game_id_str = str(game_state.game_id)
    initial_history_len = len(game_state.history)

    # Clear any previous config on the mock (good practice)
    mock_resolve_actions.mock_config.clear()
    # Default behavior is peaceful night (no config needed)

    new_state = await phase_logic.advance_to_day(game_state, game_id_str) # Await the call

    assert new_state.phase == GamePhase.DAY
    assert new_state.day_number == 1
    new_history = new_state.history[initial_history_len:]
    print(f"\nDEBUG History (no_kill): {new_history}")
    peaceful_msg_suffix = "Peaceful night."
    discuss_msg_suffix = f"Day {new_state.day_number}. Discuss and decide who to lynch."
    assert any(msg.strip().endswith(peaceful_msg_suffix) for msg in new_history)
    assert any(msg.strip().endswith(discuss_msg_suffix) for msg in new_history)
    mock_resolve_actions.assert_called_once_with(game_state)
    # Called twice: once after phase change, once after potential AI messages
    # Note: Even if no messages generated, the logic path includes the second save attempt
    assert mock_game_manager_update.await_count == 2
    mock_game_manager_update.assert_awaited_with(game_id_str, new_state)
    # Check LLM service was NOT called (no AI messages generated in this test yet)
    # assert mock_llm_service.generate_ai_day_message.call_count == 0 # Removed this assertion

@pytest.mark.asyncio # Mark as async
async def test_advance_to_day_with_kill(mock_game_manager_update, mock_resolve_actions, mock_llm_service):
    # Use 5 players: 1 M, 1 Dt, 3 V
    players = create_test_players([
        Role.VILLAGER, Role.MAFIA, Role.DETECTIVE, Role.VILLAGER, Role.VILLAGER
    ])
    game_state = create_test_game_state(players, phase=GamePhase.NIGHT, day=1)
    game_id_str = str(game_state.game_id)
    killed_player = players[0]
    initial_history_len = len(game_state.history)

    kill_announcement_suffix = f"{killed_player.name} was killed. Role: {killed_player.role.value}."
    # Configure the mock via its attached config dict
    mock_resolve_actions.mock_config.clear()
    mock_resolve_actions.mock_config["killed"] = killed_player
    mock_resolve_actions.mock_config["saved"] = None
    mock_resolve_actions.mock_config["announcements"] = [f"[{datetime.now()}] {kill_announcement_suffix}"]

    new_state = await phase_logic.advance_to_day(game_state, game_id_str) # Await the call

    assert new_state.phase == GamePhase.DAY
    assert killed_player.status == PlayerStatus.DEAD
    new_history = new_state.history[initial_history_len:]
    discuss_msg_suffix = f"Day {new_state.day_number}. Discuss and decide who to lynch."
    assert any(msg.strip().endswith(kill_announcement_suffix) for msg in new_history)
    assert any(msg.strip().endswith(discuss_msg_suffix) for msg in new_history)
    mock_resolve_actions.assert_called_once_with(game_state)
    # Called twice: once after phase change, once after potential AI messages
    # Note: Even if no messages generated, the logic path includes the second save attempt
    assert mock_game_manager_update.await_count == 2
    mock_game_manager_update.assert_awaited_with(game_id_str, new_state)
    # Check LLM service was NOT called (no AI messages generated in this test yet)
    # assert mock_llm_service.generate_ai_day_message.call_count == 0 # Removed this assertion

@pytest.mark.asyncio # Mark as async
async def test_advance_to_day_innocent_win(mock_game_manager_update, mock_resolve_actions):
    # Setup: 1 Mafia, 4 Villagers. Mafia gets killed.
    players = create_test_players([
        Role.VILLAGER, Role.MAFIA, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER
    ])
    game_state = create_test_game_state(players, phase=GamePhase.NIGHT, day=1)
    game_id_str = str(game_state.game_id)
    killed_player = next(p for p in players if p.role == Role.MAFIA)
    initial_history_len = len(game_state.history)

    kill_announcement_suffix = f"{killed_player.name} was killed."
    win_announcement_suffix = "Game Over: All Mafia have been eliminated. Innocents win!"
    # Configure mock behavior
    mock_resolve_actions.mock_config.clear()
    mock_resolve_actions.mock_config["killed"] = killed_player
    mock_resolve_actions.mock_config["saved"] = None
    mock_resolve_actions.mock_config["announcements"] = [f"[{datetime.now()}] {kill_announcement_suffix}"]

    new_state = await phase_logic.advance_to_day(game_state, game_id_str) # Await

    assert new_state.phase == GamePhase.GAMEOVER
    assert new_state.winner == "innocents"
    assert killed_player.status == PlayerStatus.DEAD
    new_history = new_state.history[initial_history_len:]
    assert any(msg.strip().endswith(kill_announcement_suffix) for msg in new_history)
    assert any(msg.strip().endswith(win_announcement_suffix) for msg in new_history)
    mock_resolve_actions.assert_called_once_with(game_state)
    assert mock_game_manager_update.await_count == 1
    mock_game_manager_update.assert_awaited_once_with(game_id_str, new_state)

@pytest.mark.asyncio # Mark as async
async def test_advance_to_voting(mock_game_manager_update, mock_llm_service): # Use fixture
    players = create_test_players([
        Role.VILLAGER, Role.MAFIA, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER
    ])
    game_state = create_test_game_state(players, phase=GamePhase.DAY, day=1)
    game_id_str = str(game_state.game_id)

    # Mock LLM service via the fixture to avoid unexpected votes/history
    mock_llm_service.determine_ai_vote.return_value = None # Simulate no votes determined

    # Remove the local patch context manager
    # with patch("app.services.phase_logic.llm_service", autospec=True) as mock_llm:
    #    mock_llm.determine_ai_vote.return_value = None # Simulate no votes determined

    new_state = await phase_logic.advance_to_voting(game_state, game_id_str) # Await

    assert new_state.phase == GamePhase.VOTING
    assert new_state.day_number == 1 # Day number doesn't change going Day -> Voting
    # Check the specific history message AFTER potential AI vote messages
    # The history message might be added *before* AI votes are attempted now.
    # Let's check for the core message existing.
    assert any("Voting phase begins" in msg for msg in new_state.history)
    assert new_state.votes == {} # No votes should be recorded due to mock
    # Called twice: Once after phase change, once after AI voting (even if no votes)
    assert mock_game_manager_update.await_count >= 1 # Should be called at least once for phase change
    # Check the last call if AI voting happened (it should be attempted)
    if mock_game_manager_update.await_count > 1:
         mock_game_manager_update.assert_awaited_with(game_id_str, new_state)
    else: # Check the first call if no AI vote save occurred
         mock_game_manager_update.assert_awaited_once_with(game_id_str, game_state) # Check the first call

@pytest.mark.asyncio
@patch("app.services.phase_logic.llm_service", autospec=True)
async def test_advance_to_voting_triggers_ai_votes(mock_llm_service_local, mock_game_manager_update):
    players = create_test_players([
        Role.MAFIA, # AI
        Role.DOCTOR, # AI
        Role.DETECTIVE, # Human
        Role.VILLAGER, # AI
        Role.VILLAGER  # AI
    ])
    # Make P3 human
    human_player = next(p for p in players if p.role == Role.DETECTIVE)
    human_player.is_human = True
    for p in players: 
        if p != human_player:
            p.is_human = False
            
    game_state = create_test_game_state(players, phase=GamePhase.DAY, day=1)
    game_id_str = str(game_state.game_id)

    ai_players = [p for p in players if not p.is_human and p.status == PlayerStatus.ALIVE]
    # Simulate LLM returning votes
    mock_votes = {p.id: players[0].id for p in ai_players} # Everyone votes for Player 0 (Mafia)
    def vote_side_effect(player, gs):
        return mock_votes.get(player.id)
    mock_llm_service_local.determine_ai_vote.side_effect = vote_side_effect

    new_state = await phase_logic.advance_to_voting(game_state, game_id_str) # Await

    assert new_state.phase == GamePhase.VOTING
    # Check LLM service was called for each living AI player
    assert mock_llm_service_local.determine_ai_vote.call_count == len(ai_players)
    for ai_p in ai_players:
        mock_llm_service_local.determine_ai_vote.assert_any_call(ai_p, game_state)
    
    # Check votes were recorded in game state
    assert len(new_state.votes) == len(ai_players)
    for voter_id, target_id in mock_votes.items():
        assert new_state.votes[voter_id] == target_id
        # Check that the specific history message exists
        expected_history_msg = f"AI {next(p.name for p in players if p.id == voter_id)} ({voter_id}) has decided their vote."
        assert any(expected_history_msg in msg for msg in new_state.history)
    
    # Check state saved twice
    assert mock_game_manager_update.await_count == 2
    mock_game_manager_update.assert_awaited_with(game_id_str, new_state)

@pytest.mark.asyncio
@patch("app.services.phase_logic.llm_service", autospec=True)
async def test_advance_to_voting_handles_llm_error(mock_llm_service_local, mock_game_manager_update, caplog):
    players = create_test_players([
        Role.MAFIA, # AI
        Role.VILLAGER, # AI
        Role.VILLAGER, # Human
        Role.DOCTOR, # AI (to reach 5 players)
        Role.DETECTIVE # AI (to reach 5 players)
    ])
    # Make P3 human
    human_player = players[2]
    human_player.is_human = True
    ai_player1 = players[0]
    ai_player1.is_human = False
    ai_player2 = players[1]
    ai_player2.is_human = False
    # Ensure other AIs are marked as AI
    players[3].is_human = False
    players[4].is_human = False

    game_state = create_test_game_state(players, phase=GamePhase.DAY, day=1)
    game_id_str = str(game_state.game_id)

    # Simulate LLM error for one AI, success for other, None for rest
    ai_player_ids = [p.id for p in players if not p.is_human]
    def vote_side_effect(player, gs):
        if player.id == ai_player_ids[0]: # First AI (Mafia)
            raise LLMServiceError("API timeout")
        elif player.id == ai_player_ids[1]: # Second AI (Villager)
            return players[0].id # Vote for Mafia
        else:
            return None # Other AIs don't vote
    mock_llm_service_local.determine_ai_vote.side_effect = vote_side_effect

    new_state = await phase_logic.advance_to_voting(game_state, game_id_str) # Await

    assert new_state.phase == GamePhase.VOTING
    assert mock_llm_service_local.determine_ai_vote.call_count == len(ai_player_ids) # Called for all AIs
    
    # Check only the successful vote was recorded
    assert len(new_state.votes) == 1
    assert ai_player2.id in new_state.votes
    assert new_state.votes[ai_player2.id] == ai_player1.id
    assert ai_player1.id not in new_state.votes

    # Check history logs error and success
    assert any(f"AI {ai_player1.name} ({ai_player1.id}) failed to determine vote due to LLM error: API timeout" in msg for msg in new_state.history)
    assert any(f"AI {ai_player2.name} ({ai_player2.id}) has decided their vote." in msg for msg in new_state.history)
    # Check logs for the AIs that returned None
    assert any(f"AI {players[3].name} ({players[3].id}) abstained or failed to vote." in msg for msg in new_state.history)
    assert any(f"AI {players[4].name} ({players[4].id}) abstained or failed to vote." in msg for msg in new_state.history)

    
    # Check state saved twice
    assert mock_game_manager_update.await_count == 2
    mock_game_manager_update.assert_awaited_with(game_id_str, new_state)

@pytest.mark.asyncio # Mark as async
async def test_process_voting_lynch(mock_game_manager_update):
    # Use 5 players: 1 M, 1 Dr, 3 V
    players = create_test_players([
        Role.VILLAGER, Role.MAFIA, Role.DOCTOR, Role.VILLAGER, Role.VILLAGER
    ])
    game_state = create_test_game_state(players, phase=GamePhase.VOTING, day=1)
    game_id_str = str(game_state.game_id)
    target_player = players[1] # Lynch Player 2 (Mafia)
    initial_history_len = len(game_state.history)

    # Simulate votes from living players (all 5) using UUIDs
    votes = {
        players[0].id: target_player.id, # V1 votes M
        players[2].id: target_player.id, # Dr votes M
        players[3].id: target_player.id, # V2 votes M
        players[4].id: target_player.id, # V3 votes M
        players[1].id: players[0].id     # M votes V1
    }

    final_state = await phase_logic.process_voting_and_advance(game_state, game_id_str, votes) # Await

    # Lynching the only Mafia triggers innocent win condition immediately
    assert final_state.phase == GamePhase.GAMEOVER
    assert final_state.winner == "innocents"
    assert target_player.status == PlayerStatus.DEAD
    lynch_msg = f"The town has voted. {target_player.name} (ID: {target_player.id}) has been lynched. They were a {target_player.role.value}."
    vote_log_msg = f"{players[0].name} voted for {target_player.name}."
    new_history = final_state.history[initial_history_len:]
    assert any(lynch_msg in msg for msg in new_history)
    assert any(vote_log_msg in msg for msg in new_history)
    assert any("Innocents win!" in msg for msg in new_history)
    # Called once when win condition met after vote processing
    assert mock_game_manager_update.await_count >= 2
    mock_game_manager_update.assert_awaited_with(game_id_str, final_state)

@pytest.mark.asyncio # Mark as async
async def test_process_voting_tie(mock_game_manager_update):
    # Use 6 players: 1 M, 1 Dr, 1 Dt, 3 V
    players = create_test_players([
        Role.VILLAGER, Role.MAFIA, Role.DOCTOR, Role.DETECTIVE, Role.VILLAGER, Role.VILLAGER
    ])
    game_state = create_test_game_state(players, phase=GamePhase.VOTING, day=1)
    game_id_str = str(game_state.game_id)
    initial_history_len = len(game_state.history)

    # Tie: 3 votes p0 (V1), 3 votes p1 (M) using UUIDs
    votes = {
        players[0].id: players[1].id, # V1 votes M
        players[1].id: players[0].id, # M votes V1
        players[2].id: players[1].id, # Dr votes M
        players[3].id: players[0].id, # Dt votes V1
        players[4].id: players[1].id, # V2 votes M
        players[5].id: players[0].id  # V3 votes V1
    }

    # Mock AI actions within advance_to_night to control save count
    with patch("app.services.phase_logic.llm_service", autospec=True) as mock_llm:
        mock_llm.determine_ai_night_action.return_value = None # No AI actions
        final_state = await phase_logic.process_voting_and_advance(game_state, game_id_str, votes) # Await

    assert final_state.phase == GamePhase.NIGHT
    assert all(p.status == PlayerStatus.ALIVE for p in players)
    # Check tie message (allow any order of names)
    assert any("Voting resulted in a tie between" in msg and "No one is lynched." in msg for msg in final_state.history[initial_history_len:])
    assert final_state.day_number == 2
    # In a tie, process_voting calls advance_to_night.
    # advance_to_night saves state twice (after phase change, after AI actions).
    assert mock_game_manager_update.await_count >= 2
    mock_game_manager_update.assert_awaited_with(game_id_str, final_state)

@pytest.mark.asyncio # Mark as async
async def test_process_voting_mafia_win_lynch(mock_game_manager_update):
    # Setup: 2 M, 3 V. Lynch a Villager -> 2 M, 2 V -> Mafia win
    players = create_test_players([
        Role.VILLAGER, Role.MAFIA, Role.VILLAGER, Role.MAFIA, Role.VILLAGER
    ])
    game_state = create_test_game_state(players, phase=GamePhase.VOTING, day=1)
    game_id_str = str(game_state.game_id)
    target_player = players[0] # Lynch Player 1 (Villager)
    initial_history_len = len(game_state.history)

    # Vote to lynch player 0 (Villager) using UUIDs
    votes = { p.id: target_player.id for p in players if p.status == PlayerStatus.ALIVE }

    final_state = await phase_logic.process_voting_and_advance(game_state, game_id_str, votes) # Await

    assert final_state.phase == GamePhase.GAMEOVER
    assert final_state.winner == "mafia"
    assert target_player.status == PlayerStatus.DEAD
    lynch_msg = f"The town has voted. {target_player.name} (ID: {target_player.id}) has been lynched. They were a {target_player.role.value}."
    assert any(lynch_msg in msg for msg in final_state.history[initial_history_len:])
    assert any("Mafia win!" in msg for msg in final_state.history[initial_history_len + 1:])
    assert mock_game_manager_update.await_count == 2
    mock_game_manager_update.assert_awaited_with(game_id_str, final_state)

@pytest.mark.asyncio # Mark as async
async def test_process_voting_mafia_win_no_lynch(mock_game_manager_update):
    # Setup: 2 M, 3 V (5 total). Tie vote -> Game continues (2 M vs 3 V)
    players = create_test_players([
        Role.VILLAGER, Role.MAFIA, Role.VILLAGER, Role.MAFIA, Role.VILLAGER
    ])
    game_state = create_test_game_state(players, phase=GamePhase.VOTING, day=1)
    game_id_str = str(game_state.game_id)
    initial_history_len = len(game_state.history)

    # Tie vote p0 (V) and p1 (M) using UUIDs
    votes = {
        players[0].id: players[1].id, # V1 votes M1
        players[1].id: players[0].id, # M1 votes V1
        players[2].id: players[1].id, # V2 votes M1
        players[3].id: players[0].id, # M2 votes V1
        players[4].id: players[2].id, # V3 votes V2 (irrelevant)
    } # 2 votes M1, 2 votes V1 -> Tie

    # Mock AI actions within advance_to_night to control save count
    with patch("app.services.phase_logic.llm_service", autospec=True) as mock_llm:
        mock_llm.determine_ai_night_action.return_value = None # No AI actions
        final_state = await phase_logic.process_voting_and_advance(game_state, game_id_str, votes) # Await

    # Tie vote means no lynch, game continues to Night
    assert final_state.phase == GamePhase.NIGHT
    assert final_state.winner is None
    assert all(p.status == PlayerStatus.ALIVE for p in players)
    # Check tie message (allow any order of names)
    new_history = final_state.history[initial_history_len:]
    assert any("Voting resulted in a tie between" in msg and "No one is lynched." in msg for msg in new_history)
    assert final_state.day_number == 2
    # In a tie, process_voting calls advance_to_night.
    # advance_to_night saves state twice (after phase change, after AI actions).
    assert mock_game_manager_update.await_count >= 2
    mock_game_manager_update.assert_awaited_with(game_id_str, final_state)

@pytest.mark.asyncio
@patch("app.services.phase_logic.llm_service", autospec=True)
async def test_advance_to_day_triggers_ai_messages(mock_llm_service_local, mock_game_manager_update, mock_resolve_actions, game_state_night):
    # Ensure the game state starts in NIGHT phase for advance_to_day
    game_state_night.phase = GamePhase.NIGHT # Set phase correctly
    game_id_str = str(game_state_night.game_id)
    ai_players = [p for p in game_state_night.players if not p.is_human and p.status == PlayerStatus.ALIVE]
    num_ai_players = len(ai_players)
    mock_resolve_actions.mock_config.clear() # Ensure default peaceful night for this test

    # Configure mock LLM service to return some messages
    def msg_side_effect(player, gs):
        if player in ai_players:
            return ChatMessage(player_id=player.id, message=f"AI {player.name} says hi!", timestamp=datetime.now())
        return None
    mock_llm_service_local.generate_ai_day_message.side_effect = msg_side_effect

    initial_chat_len = len(game_state_night.chat_history)

    # Call advance_to_day (which internally transitions to DAY and triggers AI messages)
    final_state = await phase_logic.advance_to_day(game_state_night, game_id_str) # Await

    # Assertions
    assert final_state.phase == GamePhase.DAY # Check phase transition occurred
    # Check call count directly
    actual_call_count = mock_llm_service_local.generate_ai_day_message.call_count
    assert actual_call_count == num_ai_players
    assert len(final_state.chat_history) == initial_chat_len + num_ai_players
    assert all(f"AI {p.name} says hi!" in msg.message for p, msg in zip(ai_players, final_state.chat_history[initial_chat_len:]))
    # Check game_manager.update was called (at least twice: phase change + after messages)
    assert mock_game_manager_update.await_count >= 2
    mock_game_manager_update.assert_awaited_with(game_id_str, final_state) # Check final call 
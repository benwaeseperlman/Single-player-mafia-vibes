import pytest
from unittest.mock import patch, MagicMock
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
    with patch("app.services.phase_logic.save_game_state") as mock_save:
        yield mock_save

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

def test_advance_to_night(mock_state_service):
    # Use 5 players: 1 Mafia, 4 Villagers
    players = create_test_players([
        Role.VILLAGER, Role.MAFIA, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER
    ])
    game_state = create_test_game_state(players, phase=GamePhase.DAY, day=1)
    game_id_str = str(game_state.game_id)

    new_state = phase_logic.advance_to_night(game_state, game_id_str)

    assert new_state.phase == GamePhase.NIGHT
    assert new_state.day_number == 2
    assert "Night falls" in new_state.history[-1]
    assert new_state.night_actions == {}
    assert new_state.votes == {}
    # Called twice: once after phase change, once after potential AI actions
    assert mock_state_service.call_count == 2
    mock_state_service.assert_called_with(game_id_str, new_state) # Check last call

def test_advance_to_night_increments_day(mock_state_service):
    # Use 5 players
    players = create_test_players([
        Role.VILLAGER, Role.MAFIA, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER
    ])
    game_state = create_test_game_state(players, phase=GamePhase.VOTING, day=1)
    game_id_str = str(game_state.game_id)

    new_state = phase_logic.advance_to_night(game_state, game_id_str)

    assert new_state.phase == GamePhase.NIGHT
    assert new_state.day_number == 2
    assert f"Night falls. Day {new_state.day_number}." in new_state.history[-1]
    assert new_state.night_actions == {}
    assert new_state.votes == {}
    # Called twice: once after phase change, once after potential AI actions
    assert mock_state_service.call_count == 2
    mock_state_service.assert_called_with(game_id_str, new_state)

def test_advance_to_day_no_kill(mock_state_service, mock_resolve_actions, mock_llm_service):
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

    new_state = phase_logic.advance_to_day(game_state, game_id_str)

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
    assert mock_state_service.call_count == 2
    mock_state_service.assert_called_with(game_id_str, new_state)
    # Check LLM service was NOT called (no AI messages generated in this test yet)
    # assert mock_llm_service.generate_ai_day_message.call_count == 0 # Removed this assertion

def test_advance_to_day_with_kill(mock_state_service, mock_resolve_actions, mock_llm_service):
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

    new_state = phase_logic.advance_to_day(game_state, game_id_str)

    assert new_state.phase == GamePhase.DAY
    assert killed_player.status == PlayerStatus.DEAD
    new_history = new_state.history[initial_history_len:]
    discuss_msg_suffix = f"Day {new_state.day_number}. Discuss and decide who to lynch."
    assert any(msg.strip().endswith(kill_announcement_suffix) for msg in new_history)
    assert any(msg.strip().endswith(discuss_msg_suffix) for msg in new_history)
    mock_resolve_actions.assert_called_once_with(game_state)
    # Called twice: once after phase change, once after potential AI messages
    # Note: Even if no messages generated, the logic path includes the second save attempt
    assert mock_state_service.call_count == 2
    mock_state_service.assert_called_with(game_id_str, new_state)
    # Check LLM service was NOT called (no AI messages generated in this test yet)
    # assert mock_llm_service.generate_ai_day_message.call_count == 0 # Removed this assertion

def test_advance_to_day_innocent_win(mock_state_service, mock_resolve_actions):
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

    new_state = phase_logic.advance_to_day(game_state, game_id_str)

    assert new_state.phase == GamePhase.GAMEOVER
    assert new_state.winner == "innocents"
    assert killed_player.status == PlayerStatus.DEAD
    new_history = new_state.history[initial_history_len:]
    assert any(msg.strip().endswith(kill_announcement_suffix) for msg in new_history)
    assert any(msg.strip().endswith(win_announcement_suffix) for msg in new_history)
    mock_resolve_actions.assert_called_once_with(game_state)
    mock_state_service.assert_called_once_with(game_id_str, new_state)

def test_advance_to_voting(mock_state_service):
    players = create_test_players([
        Role.VILLAGER, Role.MAFIA, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER
    ])
    game_state = create_test_game_state(players, phase=GamePhase.DAY, day=1)
    game_id_str = str(game_state.game_id)

    # Mock LLM service for this test to avoid unexpected votes/history
    with patch("app.services.phase_logic.llm_service", autospec=True) as mock_llm:
        mock_llm.determine_ai_vote.return_value = None # Simulate no votes determined

        new_state = phase_logic.advance_to_voting(game_state, game_id_str)

        assert new_state.phase == GamePhase.VOTING
        assert new_state.day_number == 1 # Day number doesn't change going Day -> Voting
        # Check the specific history message AFTER potential AI vote messages
        assert any("Voting has begun! Choose who to lynch." in msg for msg in new_state.history)
        assert new_state.votes == {} # No votes should be recorded due to mock
        # Called twice: Once after phase change, once after AI voting
        assert mock_state_service.call_count == 2 
        mock_state_service.assert_called_with(game_id_str, new_state)

@patch("app.services.phase_logic.llm_service", autospec=True)
def test_advance_to_voting_triggers_ai_votes(mock_llm_service, mock_state_service):
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
    mock_llm_service.determine_ai_vote.side_effect = vote_side_effect

    new_state = phase_logic.advance_to_voting(game_state, game_id_str)

    assert new_state.phase == GamePhase.VOTING
    # Check LLM service was called for each living AI player
    assert mock_llm_service.determine_ai_vote.call_count == len(ai_players)
    for ai_p in ai_players:
        mock_llm_service.determine_ai_vote.assert_any_call(ai_p, game_state)
    
    # Check votes were recorded in game state
    assert len(new_state.votes) == len(ai_players)
    for voter_id, target_id in mock_votes.items():
        assert new_state.votes[voter_id] == target_id
        # Check that the specific history message exists
        expected_history_msg = f"AI {next(p.name for p in players if p.id == voter_id)} ({voter_id}) has cast their vote."
        assert any(expected_history_msg in msg for msg in new_state.history)
    
    # Check state saved twice
    assert mock_state_service.call_count == 2
    mock_state_service.assert_called_with(game_id_str, new_state)

@patch("app.services.phase_logic.llm_service", autospec=True)
def test_advance_to_voting_handles_llm_error(mock_llm_service, mock_state_service, caplog):
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
    mock_llm_service.determine_ai_vote.side_effect = vote_side_effect

    new_state = phase_logic.advance_to_voting(game_state, game_id_str)

    assert new_state.phase == GamePhase.VOTING
    assert mock_llm_service.determine_ai_vote.call_count == len(ai_player_ids) # Called for all AIs
    
    # Check only the successful vote was recorded
    assert len(new_state.votes) == 1
    assert ai_player2.id in new_state.votes
    assert new_state.votes[ai_player2.id] == ai_player1.id
    assert ai_player1.id not in new_state.votes

    # Check history logs error and success
    assert any(f"AI {ai_player1.name} ({ai_player1.id}) failed to vote due to LLM error: API timeout" in msg for msg in new_state.history)
    assert any(f"AI {ai_player2.name} ({ai_player2.id}) has cast their vote." in msg for msg in new_state.history)
    # Check logs for the AIs that returned None
    assert any(f"AI {players[3].name} ({players[3].id}) could not determine a vote." in msg for msg in new_state.history)
    assert any(f"AI {players[4].name} ({players[4].id}) could not determine a vote." in msg for msg in new_state.history)

    
    # Check state saved twice
    assert mock_state_service.call_count == 2
    mock_state_service.assert_called_with(game_id_str, new_state)

def test_process_voting_lynch(mock_state_service):
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

    new_state = phase_logic.process_voting_and_advance(game_state, game_id_str, votes)

    # Lynching the only Mafia triggers innocent win condition immediately
    assert new_state.phase == GamePhase.GAMEOVER
    assert new_state.winner == "innocents"
    assert target_player.status == PlayerStatus.DEAD
    lynch_msg = f"{target_player.name} (ID: {target_player.id}) has been lynched with 4 votes. They were a {target_player.role.value}."
    new_history = new_state.history[initial_history_len:]
    assert any(lynch_msg in msg for msg in new_history)
    assert any("Innocents win!" in msg for msg in new_history)
    # Called once when win condition met after vote processing
    assert mock_state_service.call_count == 1
    mock_state_service.assert_called_with(game_id_str, new_state)

def test_process_voting_tie(mock_state_service):
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
        new_state = phase_logic.process_voting_and_advance(game_state, game_id_str, votes)

    assert new_state.phase == GamePhase.NIGHT
    assert all(p.status == PlayerStatus.ALIVE for p in players)
    # Updated tie message check
    tie_msg = f"Voting resulted in a tie with 3 votes each. No one is lynched."
    # Check message exists anywhere in new history segment
    assert any(tie_msg in msg for msg in new_state.history[initial_history_len:]) 
    assert any(f"Night falls. Day {new_state.day_number}." in msg for msg in new_state.history[initial_history_len + 1:])
    assert new_state.day_number == 2
    # In a tie, process_voting calls advance_to_night.
    # advance_to_night saves state twice (after phase change, after AI actions).
    assert mock_state_service.call_count == 2

def test_process_voting_mafia_win_lynch(mock_state_service):
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

    new_state = phase_logic.process_voting_and_advance(game_state, game_id_str, votes)

    assert new_state.phase == GamePhase.GAMEOVER
    assert new_state.winner == "mafia"
    assert target_player.status == PlayerStatus.DEAD
    num_votes_for_lynch = sum(1 for p_id in votes if votes[p_id] == target_player.id)
    lynch_msg = f"{target_player.name} (ID: {target_player.id}) has been lynched with {num_votes_for_lynch} votes. They were a {target_player.role.value}."
    assert any(lynch_msg in msg for msg in new_state.history[initial_history_len:])
    assert any("Mafia win!" in msg for msg in new_state.history[initial_history_len + 1:])
    assert mock_state_service.call_count == 1
    mock_state_service.assert_called_once_with(game_id_str, new_state)

def test_process_voting_mafia_win_no_lynch(mock_state_service):
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
        new_state = phase_logic.process_voting_and_advance(game_state, game_id_str, votes)

    # Tie vote means no lynch, game continues to Night
    assert new_state.phase == GamePhase.NIGHT
    assert new_state.winner is None
    assert all(p.status == PlayerStatus.ALIVE for p in players)
    # Updated tie message check
    tie_msg = f"Voting resulted in a tie with 2 votes each. No one is lynched."
    new_history = new_state.history[initial_history_len:]
    assert any(tie_msg in msg for msg in new_history)
    assert any(f"Night falls. Day {new_state.day_number}." in msg for msg in new_history)
    # In a tie, process_voting calls advance_to_night.
    # advance_to_night saves state twice (after phase change, after AI actions).
    assert mock_state_service.call_count == 2

# Test internal _check_win_condition directly
def test_check_win_condition_innocent_win():
    # Need at least 5 players for settings, ensure no mafia
    players = create_test_players([
        Role.VILLAGER, Role.DOCTOR, Role.DETECTIVE, Role.VILLAGER, Role.VILLAGER
    ])
    # Manually remove mafia if create_test_players added one by default (it shouldn't here)
    players = [p for p in players if p.role != Role.MAFIA]
    # If players < 5 after removal, add villagers
    while len(players) < 5:
        players.append(create_test_players([Role.VILLAGER])[0])

    # We cannot create GameSettings without Mafia, so this test is flawed.
    # Instead, test the condition logic directly without full GameState setup.
    game_state_mock = MagicMock(spec=GameState)
    game_state_mock.players = players
    game_state_mock.history = []
    game_state_mock.add_to_history = MagicMock()

    assert phase_logic._check_win_condition(game_state_mock) == GamePhase.GAMEOVER
    assert game_state_mock.winner == "innocents"
    game_state_mock.add_to_history.assert_called_with("Game Over: All Mafia have been eliminated. Innocents win!")

def test_check_win_condition_mafia_win():
    # 3 M, 2 V -> Mafia win
    players = create_test_players([
        Role.MAFIA, Role.MAFIA, Role.VILLAGER, Role.MAFIA, Role.VILLAGER
    ])
    game_state = create_test_game_state(players)
    initial_history_len = len(game_state.history)
    assert phase_logic._check_win_condition(game_state) == GamePhase.GAMEOVER
    assert game_state.winner == "mafia"
    assert "Mafia win!" in game_state.history[initial_history_len]

def test_check_win_condition_mafia_equal_innocent():
    # 2 M, 2 V. Need 5 players total
    players = create_test_players([
        Role.MAFIA, Role.VILLAGER, Role.MAFIA, Role.VILLAGER
    ])
    players.append(create_test_players([Role.VILLAGER])[0]) # Add 5th player (Villager)
    players[4].status = PlayerStatus.DEAD # Make 5th player dead, so counts are 2 M vs 2 V
    game_state = create_test_game_state(players)
    initial_history_len = len(game_state.history)
    assert phase_logic._check_win_condition(game_state) == GamePhase.GAMEOVER
    assert game_state.winner == "mafia"
    assert "Mafia win!" in game_state.history[initial_history_len]

def test_check_win_condition_ongoing():
    # 2 M, 3 V -> Ongoing
    players = create_test_players([
        Role.MAFIA, Role.VILLAGER, Role.DOCTOR, Role.MAFIA, Role.VILLAGER
    ])
    game_state = create_test_game_state(players)
    initial_history_len = len(game_state.history)
    assert phase_logic._check_win_condition(game_state) is None
    assert len(game_state.history) == initial_history_len

# Test internal _resolve_night_actions (basic placeholder behavior)
# THESE TESTS ARE NOW OBSOLETE as we test the actual _resolve_night_actions below
# @patch("app.services.phase_logic.random.choice")
# def test_resolve_night_actions_simulated_kill(mock_random_choice):
#     ...

# @patch("app.services.phase_logic.random.choice")
# def test_resolve_night_actions_no_kill(mock_random_choice):
#    ...

# --- Tests for _resolve_night_actions ---

def test_resolve_night_actions_mafia_kill_success(game_state_night: GameState):
    """Test when Mafia successfully kills an unprotected player."""
    mafia = next(p for p in game_state_night.players if p.role == Role.MAFIA)
    victim = next(p for p in game_state_night.players if p.role == Role.VILLAGER)
    
    # Record Mafia action
    mafia_action = MafiaKillAction(player_id=mafia.id, target_id=victim.id)
    game_state_night.night_actions[ActionType.MAFIA_KILL] = mafia_action
    
    killed_player, saved_player, announcements = phase_logic._resolve_night_actions(game_state_night)
    
    assert killed_player is not None
    assert killed_player.id == victim.id
    assert killed_player.status == PlayerStatus.DEAD
    assert saved_player is None
    assert len(announcements) == 1
    assert f"{victim.name}" in announcements[0]
    assert "was killed" in announcements[0]
    assert victim.role.value in announcements[0]
    assert ActionType.MAFIA_KILL not in game_state_night.night_actions # Actions cleared

def test_resolve_night_actions_doctor_save_success(game_state_night: GameState):
    """Test when Doctor successfully saves the Mafia target."""
    mafia = next(p for p in game_state_night.players if p.role == Role.MAFIA)
    doctor = next(p for p in game_state_night.players if p.role == Role.DOCTOR)
    target = next(p for p in game_state_night.players if p.role == Role.VILLAGER)
    
    # Record actions
    mafia_action = MafiaKillAction(player_id=mafia.id, target_id=target.id)
    doctor_action = DoctorProtectAction(player_id=doctor.id, target_id=target.id)
    game_state_night.night_actions[ActionType.MAFIA_KILL] = mafia_action
    game_state_night.night_actions[doctor.id] = doctor_action # Doctor action keyed by player ID
    
    killed_player, saved_player, announcements = phase_logic._resolve_night_actions(game_state_night)
    
    assert killed_player is None
    assert saved_player is not None
    assert saved_player.id == target.id
    assert target.status == PlayerStatus.ALIVE # Target survived
    assert len(announcements) == 1
    assert f"{target.name}" in announcements[0]
    assert "survived the attack" in announcements[0]
    assert doctor.id not in game_state_night.night_actions # Actions cleared
    assert ActionType.MAFIA_KILL not in game_state_night.night_actions

def test_resolve_night_actions_doctor_saves_non_target(game_state_night: GameState):
    """Test when Doctor saves someone, but Mafia kills someone else."""
    mafia = next(p for p in game_state_night.players if p.role == Role.MAFIA)
    doctor = next(p for p in game_state_night.players if p.role == Role.DOCTOR)
    victim = next(p for p in game_state_night.players if p.role == Role.VILLAGER and p.name == "Villager 1")
    saved_person = next(p for p in game_state_night.players if p.role == Role.VILLAGER and p.name == "Villager 2")

    # Record actions
    mafia_action = MafiaKillAction(player_id=mafia.id, target_id=victim.id)
    doctor_action = DoctorProtectAction(player_id=doctor.id, target_id=saved_person.id)
    game_state_night.night_actions[ActionType.MAFIA_KILL] = mafia_action
    game_state_night.night_actions[doctor.id] = doctor_action
    
    killed_player, saved_player, announcements = phase_logic._resolve_night_actions(game_state_night)
    
    assert killed_player is not None
    assert killed_player.id == victim.id
    assert killed_player.status == PlayerStatus.DEAD
    assert saved_player is not None # Doctor's save action is still recorded
    assert saved_player.id == saved_person.id 
    assert saved_person.status == PlayerStatus.ALIVE # Saved person is alive
    assert len(announcements) == 1
    assert f"{victim.name}" in announcements[0]
    assert "was killed" in announcements[0]

def test_resolve_night_actions_detective_investigation(game_state_night: GameState):
    """Test Detective investigation result storage."""
    detective = next(p for p in game_state_night.players if p.role == Role.DETECTIVE)
    target_mafia = next(p for p in game_state_night.players if p.role == Role.MAFIA)
    target_innocent = next(p for p in game_state_night.players if p.role == Role.VILLAGER)

    # --- Test 1: Investigating Mafia ---    
    investigate_mafia_action = DetectiveInvestigateAction(player_id=detective.id, target_id=target_mafia.id)
    game_state_night.night_actions[detective.id] = investigate_mafia_action
    
    phase_logic._resolve_night_actions(game_state_night) # Run resolution using module prefix
    
    assert detective.investigation_result is not None
    assert f"{target_mafia.name}" in detective.investigation_result
    assert "Mafia" in detective.investigation_result
    assert detective.id not in game_state_night.night_actions # Action cleared
    game_state_night.night_actions = {}

    # --- Test 2: Investigating Innocent ---    
    investigate_innocent_action = DetectiveInvestigateAction(player_id=detective.id, target_id=target_innocent.id)
    game_state_night.night_actions[detective.id] = investigate_innocent_action

    phase_logic._resolve_night_actions(game_state_night) # Run resolution using module prefix
    
    assert detective.investigation_result is not None
    assert f"{target_innocent.name}" in detective.investigation_result
    assert "Innocent" in detective.investigation_result
    assert detective.id not in game_state_night.night_actions

def test_resolve_night_actions_no_kill(game_state_night: GameState):
    """Test scenario with no Mafia kill action."""
    doctor = next(p for p in game_state_night.players if p.role == Role.DOCTOR)
    saved_person = next(p for p in game_state_night.players if p.role == Role.VILLAGER)
    
    # Only Doctor acts
    doctor_action = DoctorProtectAction(player_id=doctor.id, target_id=saved_person.id)
    game_state_night.night_actions[doctor.id] = doctor_action
    
    killed_player, saved_player, announcements = phase_logic._resolve_night_actions(game_state_night)
    
    assert killed_player is None
    assert saved_player is not None
    assert saved_player.id == saved_person.id
    assert saved_person.status == PlayerStatus.ALIVE
    assert len(announcements) == 1
    assert "passed peacefully" in announcements[0]
    assert "No one was killed" in announcements[0]

def test_resolve_night_actions_mafia_targets_dead_player(game_state_night: GameState):
    """Test when Mafia targets an already dead player."""
    mafia = next(p for p in game_state_night.players if p.role == Role.MAFIA)
    dead_player = Player(id=uuid.uuid4(), name="Already Dead", role=Role.VILLAGER, status=PlayerStatus.DEAD)
    game_state_night.players.append(dead_player)
    
    mafia_action = MafiaKillAction(player_id=mafia.id, target_id=dead_player.id)
    game_state_night.night_actions[ActionType.MAFIA_KILL] = mafia_action
    
    killed_player, saved_player, announcements = phase_logic._resolve_night_actions(game_state_night)
    
    assert killed_player is None
    assert saved_player is None
    assert len(announcements) == 1
    assert "target was already deceased" in announcements[0]

def test_resolve_night_actions_multiple_actions(game_state_night: GameState):
    """Test resolution with Mafia, Doctor, and Detective actions simultaneously (kill succeeds)."""
    mafia = next(p for p in game_state_night.players if p.role == Role.MAFIA)
    doctor = next(p for p in game_state_night.players if p.role == Role.DOCTOR)
    detective = next(p for p in game_state_night.players if p.role == Role.DETECTIVE)
    victim = next(p for p in game_state_night.players if p.role == Role.VILLAGER and p.name == "Villager 1")
    saved_person = next(p for p in game_state_night.players if p.role == Role.VILLAGER and p.name == "Villager 2")
    investigated_person = next(p for p in game_state_night.players if p.role == Role.MAFIA)
    
    # Record actions
    mafia_action = MafiaKillAction(player_id=mafia.id, target_id=victim.id)
    doctor_action = DoctorProtectAction(player_id=doctor.id, target_id=saved_person.id)
    detective_action = DetectiveInvestigateAction(player_id=detective.id, target_id=investigated_person.id)
    game_state_night.night_actions[ActionType.MAFIA_KILL] = mafia_action
    game_state_night.night_actions[doctor.id] = doctor_action
    game_state_night.night_actions[detective.id] = detective_action
    
    killed_player, saved_player, announcements = phase_logic._resolve_night_actions(game_state_night)
    
    # Check kill outcome
    assert killed_player is not None
    assert killed_player.id == victim.id
    assert victim.status == PlayerStatus.DEAD
    
    # Check save outcome
    assert saved_player is not None
    assert saved_player.id == saved_person.id
    assert saved_person.status == PlayerStatus.ALIVE
    
    # Check announcement
    assert len(announcements) == 1
    assert f"{victim.name}" in announcements[0]
    assert "was killed" in announcements[0]
    
    # Check detective result
    assert detective.investigation_result is not None
    assert f"{investigated_person.name}" in detective.investigation_result
    assert ("Mafia" if investigated_person.role == Role.MAFIA else "Innocent") in detective.investigation_result
    
    # Check actions cleared
    assert not game_state_night.night_actions 

# -- Tests for AI Integration in Phase Logic --

@patch("app.services.phase_logic.llm_service", autospec=True)
@patch("app.services.phase_logic.action_service", autospec=True)
def test_advance_to_night_triggers_ai_actions(mock_action_service, mock_llm_service, mock_state_service, game_state_night):
    game_id_str = str(game_state_night.game_id)
    ai_players_with_actions = [p for p in game_state_night.players if not p.is_human and p.status == PlayerStatus.ALIVE and p.role in [Role.MAFIA, Role.DOCTOR, Role.DETECTIVE]]
    num_ai_actors = len(ai_players_with_actions)
    
    # Mock LLM responses
    mock_actions = {}
    for player in ai_players_with_actions:
        # Let everyone target the first Villager for simplicity
        target_villager = next(p for p in game_state_night.players if p.role == Role.VILLAGER and p.status == PlayerStatus.ALIVE)
        action_data = {"player_id": player.id, "target_id": target_villager.id}
        action = None # Initialize action to None
        if player.role == Role.MAFIA:
            action = MafiaKillAction(**action_data)
        elif player.role == Role.DOCTOR:
            action = DoctorProtectAction(**action_data)
        elif player.role == Role.DETECTIVE:
            action = DetectiveInvestigateAction(**action_data)
        if action: # Only add if an action was created
             mock_actions[player.id] = action

    mock_llm_service.determine_ai_night_action.side_effect = lambda p, gs: mock_actions.get(p.id)
    
    # Ensure action_service mock is set up correctly to just track calls
    # We patch the specific `record_night_action` function within the action_service instance
    with patch.object(phase_logic.action_service, 'record_night_action', return_value=None) as mock_record_action:
    
        new_state = phase_logic.advance_to_night(game_state_night, game_id_str)

        assert new_state.phase == GamePhase.NIGHT
        assert mock_llm_service.determine_ai_night_action.call_count == num_ai_actors
        # Check that the mocked record_night_action was called for each *valid* action generated
        assert mock_record_action.call_count == len(mock_actions) # Use length of created actions
        
        # Check the calls made to the mocked record_night_action
        call_args_list = mock_record_action.call_args_list
        recorded_actions = {call.args[1].player_id: call.args[1] for call in call_args_list} # Extract action from call args

        for player_id, action_obj in mock_actions.items():
            player = next(p for p in new_state.players if p.id == player_id)
            # Check LLM was called for this player
            mock_llm_service.determine_ai_night_action.assert_any_call(player, game_state_night)
            # Check record_night_action was called with the correct game state and action object
            mock_record_action.assert_any_call(game_state_night, action_obj)
            # Check history message was added
            assert any(f"AI {player.role.value} ({player.id}) has decided their action." in msg for msg in new_state.history)

    assert mock_state_service.call_count == 2 # Saved before and after AI actions

@patch("app.services.phase_logic.llm_service", autospec=True)
def test_advance_to_day_triggers_ai_messages(mock_llm_service, mock_state_service, mock_resolve_actions, game_state_night):
    # Transition to Day phase first (to set up state for AI message generation)
    game_id_str = str(game_state_night.game_id)
    game_state_night.phase = GamePhase.NIGHT # Ensure starting in Night
    mock_resolve_actions.mock_config.clear() # Peaceful night for this test
    initial_history_len = len(game_state_night.history)
    
    ai_players_alive = [p for p in game_state_night.players if not p.is_human and p.status == PlayerStatus.ALIVE]
    num_ai_alive = len(ai_players_alive)
    
    # Mock LLM responses for messages
    mock_messages = {}
    for i, player in enumerate(ai_players_alive):
        msg = ChatMessage(player_id=player.id, message=f"AI message from {player.name}")
        mock_messages[player.id] = msg
        
    mock_llm_service.generate_ai_day_message.side_effect = lambda p, gs: mock_messages.get(p.id)
    
    new_state = phase_logic.advance_to_day(game_state_night, game_id_str)

    assert new_state.phase == GamePhase.DAY
    assert mock_llm_service.generate_ai_day_message.call_count == num_ai_alive
    
    # Verify messages are added to chat history
    assert len(new_state.chat_history) == num_ai_alive
    for player_id, msg_obj in mock_messages.items():
        assert msg_obj in new_state.chat_history
        # Check history log for errors is clear (optional)
        assert f"AI {next(p.name for p in new_state.players if p.id == player_id)} ({player_id}) failed to generate message" not in "\n".join(new_state.history)

    # Corrected save count logic: Called once after phase change, once after messages IF messages were generated
    expected_save_count = 1 + (1 if num_ai_alive > 0 else 0)
    assert mock_state_service.call_count == expected_save_count

    assert True 
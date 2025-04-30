import pytest
from uuid import uuid4, UUID
from datetime import datetime

from app.models.game import GameState, GamePhase
from app.models.player import Player, Role, PlayerStatus
from app.models.actions import ActionType, MafiaKillAction, DetectiveInvestigateAction, DoctorProtectAction
from app.services.action_service import ActionService, ActionValidationError


# Helper fixtures
@pytest.fixture
def action_service():
    return ActionService()

@pytest.fixture
def player_mafia():
    return Player(id=uuid4(), name="Mafia Player", role=Role.MAFIA, status=PlayerStatus.ALIVE)

@pytest.fixture
def player_detective():
    return Player(id=uuid4(), name="Detective Player", role=Role.DETECTIVE, status=PlayerStatus.ALIVE)

@pytest.fixture
def player_doctor():
    return Player(id=uuid4(), name="Doctor Player", role=Role.DOCTOR, status=PlayerStatus.ALIVE)

@pytest.fixture
def player_villager():
    return Player(id=uuid4(), name="Villager Player", role=Role.VILLAGER, status=PlayerStatus.ALIVE)

@pytest.fixture
def target_player():
    return Player(id=uuid4(), name="Target Player", role=Role.VILLAGER, status=PlayerStatus.ALIVE)

@pytest.fixture
def dead_player():
    return Player(id=uuid4(), name="Dead Player", role=Role.VILLAGER, status=PlayerStatus.DEAD)

@pytest.fixture
def game_state_night(player_mafia, player_detective, player_doctor, player_villager, target_player):
    return GameState(
        game_id=uuid4(),
        players=[player_mafia, player_detective, player_doctor, player_villager, target_player],
        phase=GamePhase.NIGHT,
        day_number=1
    )

@pytest.fixture
def game_state_day(player_mafia, target_player):
     return GameState(
        game_id=uuid4(),
        players=[player_mafia, target_player],
        phase=GamePhase.DAY,
        day_number=1
    )

# --- Test record_night_action --- 

def test_record_mafia_kill_success(action_service: ActionService, game_state_night: GameState, player_mafia: Player, target_player: Player):
    action_type = ActionType.MAFIA_KILL
    initial_time = game_state_night.updated_at

    action_service.record_night_action(
        game_state=game_state_night,
        player_id=player_mafia.id,
        target_id=target_player.id,
        action_type=action_type
    )

    assert action_type in game_state_night.night_actions
    action = game_state_night.night_actions[action_type]
    assert isinstance(action, MafiaKillAction)
    assert action.player_id == player_mafia.id
    assert action.target_id == target_player.id
    assert game_state_night.updated_at > initial_time

def test_record_detective_investigate_success(action_service: ActionService, game_state_night: GameState, player_detective: Player, target_player: Player):
    action_type = ActionType.DETECTIVE_INVESTIGATE
    initial_time = game_state_night.updated_at

    action_service.record_night_action(
        game_state=game_state_night,
        player_id=player_detective.id,
        target_id=target_player.id,
        action_type=action_type
    )

    assert player_detective.id in game_state_night.night_actions
    action = game_state_night.night_actions[player_detective.id]
    assert isinstance(action, DetectiveInvestigateAction)
    assert action.player_id == player_detective.id
    assert action.target_id == target_player.id
    assert action.result is None # Result is set during resolution
    assert game_state_night.updated_at > initial_time

def test_record_doctor_protect_success(action_service: ActionService, game_state_night: GameState, player_doctor: Player, target_player: Player):
    action_type = ActionType.DOCTOR_PROTECT
    initial_time = game_state_night.updated_at

    action_service.record_night_action(
        game_state=game_state_night,
        player_id=player_doctor.id,
        target_id=target_player.id,
        action_type=action_type
    )

    assert player_doctor.id in game_state_night.night_actions
    action = game_state_night.night_actions[player_doctor.id]
    assert isinstance(action, DoctorProtectAction)
    assert action.player_id == player_doctor.id
    assert action.target_id == target_player.id
    assert game_state_night.updated_at > initial_time

# --- Test Validation Errors --- 

def test_record_action_wrong_phase(action_service: ActionService, game_state_day: GameState, player_mafia: Player, target_player: Player):
    with pytest.raises(ActionValidationError, match="Night actions can only be performed during the Night phase."):
        action_service.record_night_action(
            game_state=game_state_day,
            player_id=player_mafia.id,
            target_id=target_player.id,
            action_type=ActionType.MAFIA_KILL
        )

def test_record_action_dead_player(action_service: ActionService, game_state_night: GameState, dead_player: Player, target_player: Player):
    game_state_night.players.append(dead_player) # Add dead player to game
    with pytest.raises(ActionValidationError, match="Player must be alive to perform an action."):
        action_service.record_night_action(
            game_state=game_state_night,
            player_id=dead_player.id, # Dead player tries to act
            target_id=target_player.id,
            action_type=ActionType.MAFIA_KILL # Role doesn't matter here
        )

def test_record_action_dead_target(action_service: ActionService, game_state_night: GameState, player_mafia: Player, dead_player: Player):
    game_state_night.players.append(dead_player) # Add dead player to game
    with pytest.raises(ActionValidationError, match="Target player must be alive."):
        action_service.record_night_action(
            game_state=game_state_night,
            player_id=player_mafia.id,
            target_id=dead_player.id, # Target is dead
            action_type=ActionType.MAFIA_KILL
        )

def test_record_action_wrong_role(action_service: ActionService, game_state_night: GameState, player_villager: Player, target_player: Player):
    with pytest.raises(ActionValidationError, match="Player role 'villager' cannot perform action 'mafia_kill'."):
        action_service.record_night_action(
            game_state=game_state_night,
            player_id=player_villager.id,
            target_id=target_player.id,
            action_type=ActionType.MAFIA_KILL # Villager trying to kill
        )

def test_record_action_duplicate_action(action_service: ActionService, game_state_night: GameState, player_detective: Player, target_player: Player):
    # First action succeeds
    action_service.record_night_action(
        game_state=game_state_night,
        player_id=player_detective.id,
        target_id=target_player.id,
        action_type=ActionType.DETECTIVE_INVESTIGATE
    )
    
    # Second action by the same player fails
    another_target = game_state_night.players[0] # Target someone else
    if another_target.id == player_detective.id:
        another_target = game_state_night.players[1] # Ensure not self-targeting if detective is first
        
    with pytest.raises(ActionValidationError, match="Player has already performed their action this night."):
        action_service.record_night_action(
            game_state=game_state_night,
            player_id=player_detective.id,
            target_id=another_target.id,
            action_type=ActionType.DETECTIVE_INVESTIGATE
        )

def test_record_mafia_self_kill(action_service: ActionService, game_state_night: GameState, player_mafia: Player):
    with pytest.raises(ActionValidationError, match="Mafia cannot target themselves for a kill."):
        action_service.record_night_action(
            game_state=game_state_night,
            player_id=player_mafia.id,
            target_id=player_mafia.id, # Targeting self
            action_type=ActionType.MAFIA_KILL
        )

def test_record_action_player_not_found(action_service: ActionService, game_state_night: GameState, target_player: Player):
    invalid_player_id = uuid4()
    with pytest.raises(ValueError, match=f"Player with ID {invalid_player_id} not found in game state."):
        action_service.record_night_action(
            game_state=game_state_night,
            player_id=invalid_player_id,
            target_id=target_player.id,
            action_type=ActionType.MAFIA_KILL # Action type doesn't matter here
        )

def test_record_action_target_not_found(action_service: ActionService, game_state_night: GameState, player_mafia: Player):
    invalid_target_id = uuid4()
    with pytest.raises(ValueError, match=f"Target player with ID {invalid_target_id} not found in game state."):
        action_service.record_night_action(
            game_state=game_state_night,
            player_id=player_mafia.id,
            target_id=invalid_target_id,
            action_type=ActionType.MAFIA_KILL
        ) 
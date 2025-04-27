import pytest
from uuid import UUID
from datetime import datetime
from pydantic import ValidationError

from app.models.game import GamePhase, GameState
from app.models.player import Player, Role, PlayerStatus


def test_game_phase_enum():
    """Test that GamePhase enum contains the expected values."""
    assert GamePhase.PREGAME.value == "pregame"
    assert GamePhase.NIGHT.value == "night"
    assert GamePhase.DAY.value == "day"
    assert GamePhase.VOTING.value == "voting"
    assert GamePhase.GAMEOVER.value == "gameover"
    
    # Test enum conversion from string
    assert GamePhase("pregame") == GamePhase.PREGAME
    assert GamePhase("night") == GamePhase.NIGHT
    assert GamePhase("day") == GamePhase.DAY
    assert GamePhase("voting") == GamePhase.VOTING
    assert GamePhase("gameover") == GamePhase.GAMEOVER


def test_game_state_creation():
    """Test that a GameState can be created with valid data."""
    game_state = GameState()
    
    # Check default values
    assert isinstance(game_state.game_id, UUID)
    assert game_state.players == []
    assert game_state.phase == GamePhase.PREGAME
    assert game_state.day_number == 0
    assert game_state.settings_id is None
    assert game_state.history == []
    assert game_state.night_actions == {}
    assert game_state.votes == {}
    assert isinstance(game_state.created_at, datetime)
    assert isinstance(game_state.updated_at, datetime)
    assert game_state.winner is None


def test_game_state_with_players():
    """Test that a GameState can be created with players."""
    player1 = Player(name="Player 1", role=Role.MAFIA)
    player2 = Player(name="Player 2", role=Role.DETECTIVE)
    player3 = Player(name="Player 3", role=Role.VILLAGER)
    
    game_state = GameState(players=[player1, player2, player3])
    
    assert len(game_state.players) == 3
    assert game_state.players[0].name == "Player 1"
    assert game_state.players[0].role == Role.MAFIA
    assert game_state.players[1].name == "Player 2"
    assert game_state.players[1].role == Role.DETECTIVE
    assert game_state.players[2].name == "Player 3"
    assert game_state.players[2].role == Role.VILLAGER


def test_game_state_add_to_history():
    """Test the add_to_history method of GameState."""
    game_state = GameState()
    
    # Record the updated_at time before adding to history
    before_update = game_state.updated_at
    
    # Add an event to history
    game_state.add_to_history("Game created")
    
    # Check that the event was added
    assert len(game_state.history) == 1
    assert "Game created" in game_state.history[0]
    
    # Check that updated_at was updated
    assert game_state.updated_at > before_update


def test_game_state_serialization():
    """Test that a GameState can be serialized to and from JSON."""
    player1 = Player(name="Player 1", role=Role.MAFIA)
    player2 = Player(name="Player 2", role=Role.DETECTIVE)
    
    game_state = GameState(
        players=[player1, player2],
        phase=GamePhase.NIGHT,
        day_number=1,
        history=["Game started", "Night 1 begins"]
    )
    
    # Convert to dict (JSON serializable)
    game_dict = game_state.model_dump()
    
    # Check fields were serialized correctly
    assert isinstance(game_dict["game_id"], str)
    assert len(game_dict["players"]) == 2
    assert game_dict["players"][0]["name"] == "Player 1"
    assert game_dict["players"][0]["role"] == "mafia"
    assert game_dict["phase"] == "night"
    assert game_dict["day_number"] == 1
    assert game_dict["history"] == ["Game started", "Night 1 begins"]
    
    # Recreate from dict
    recreated_game = GameState(**game_dict)
    
    # Check fields were deserialized correctly
    assert recreated_game.game_id == game_state.game_id
    assert len(recreated_game.players) == 2
    assert recreated_game.players[0].name == "Player 1"
    assert recreated_game.players[0].role == Role.MAFIA
    assert recreated_game.players[1].name == "Player 2"
    assert recreated_game.players[1].role == Role.DETECTIVE
    assert recreated_game.phase == GamePhase.NIGHT
    assert recreated_game.day_number == 1
    assert recreated_game.history == ["Game started", "Night 1 begins"]


def test_game_state_validation():
    """Test that GameState validation works as expected."""
    # Invalid phase
    with pytest.raises(ValidationError):
        GameState(phase="invalid_phase")
    
    # Invalid day number (must be non-negative)
    with pytest.raises(ValidationError):
        GameState(day_number=-1)
    
    # Valid day number
    game_state = GameState(day_number=0)
    assert game_state.day_number == 0 
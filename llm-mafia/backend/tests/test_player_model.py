import pytest
from uuid import UUID
from pydantic import ValidationError

from app.models.player import Role, PlayerStatus, Player


def test_role_enum():
    """Test that Role enum contains the expected values."""
    assert Role.MAFIA.value == "mafia"
    assert Role.DETECTIVE.value == "detective"
    assert Role.DOCTOR.value == "doctor"
    assert Role.VILLAGER.value == "villager"
    
    # Test enum conversion from string
    assert Role("mafia") == Role.MAFIA
    assert Role("detective") == Role.DETECTIVE
    assert Role("doctor") == Role.DOCTOR
    assert Role("villager") == Role.VILLAGER


def test_player_status_enum():
    """Test that PlayerStatus enum contains the expected values."""
    assert PlayerStatus.ALIVE.value == "alive"
    assert PlayerStatus.DEAD.value == "dead"
    
    # Test enum conversion from string
    assert PlayerStatus("alive") == PlayerStatus.ALIVE
    assert PlayerStatus("dead") == PlayerStatus.DEAD


def test_player_model_creation():
    """Test that a Player can be created with valid data."""
    player = Player(
        name="Test Player",
        role=Role.VILLAGER
    )
    
    assert player.name == "Test Player"
    assert player.role == Role.VILLAGER
    assert player.status == PlayerStatus.ALIVE  # Default value
    assert player.is_human == False  # Default value
    assert player.persona_id is None  # Default value
    assert isinstance(player.id, UUID)  # Should generate a UUID


def test_player_model_serialization():
    """Test that a Player can be serialized to and from JSON."""
    player = Player(
        name="Test Player",
        role=Role.MAFIA,
        status=PlayerStatus.DEAD,
        is_human=True
    )
    
    # Convert to dict (JSON serializable)
    player_dict = player.model_dump()
    
    # Check fields were serialized correctly
    assert player_dict["name"] == "Test Player"
    assert player_dict["role"] == "mafia"
    assert player_dict["status"] == "dead"
    assert player_dict["is_human"] == True
    assert player_dict["persona_id"] is None
    
    # Recreate from dict
    recreated_player = Player(**player_dict)
    
    # Check fields were deserialized correctly
    assert recreated_player.name == player.name
    assert recreated_player.role == player.role
    assert recreated_player.status == player.status
    assert recreated_player.is_human == player.is_human
    assert recreated_player.persona_id == player.persona_id
    assert recreated_player.id == player.id


def test_player_model_validation():
    """Test that Player validation works as expected."""
    # Missing required field
    with pytest.raises(ValidationError):
        Player(role=Role.VILLAGER)  # Missing name
    
    # Invalid role
    with pytest.raises(ValidationError):
        Player(name="Test Player", role="invalid_role")
    
    # Invalid status
    with pytest.raises(ValidationError):
        Player(name="Test Player", role=Role.VILLAGER, status="invalid_status") 
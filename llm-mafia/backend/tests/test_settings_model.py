import pytest
from uuid import UUID
from pydantic import ValidationError

from app.models.settings import DoctorRules, GameSettings
from app.models.player import Role


def test_doctor_rules_enum():
    """Test that DoctorRules enum contains the expected values."""
    assert DoctorRules.STANDARD.value == "standard"
    assert DoctorRules.NO_SELF_PROTECTION.value == "no_self_protection"
    assert DoctorRules.NO_CONSECUTIVE.value == "no_consecutive"
    
    # Test enum conversion from string
    assert DoctorRules("standard") == DoctorRules.STANDARD
    assert DoctorRules("no_self_protection") == DoctorRules.NO_SELF_PROTECTION
    assert DoctorRules("no_consecutive") == DoctorRules.NO_CONSECUTIVE


def test_game_settings_creation():
    """Test that GameSettings can be created with valid data."""
    # Test with minimum required values
    settings = GameSettings(player_count=5)
    
    assert isinstance(settings.id, UUID)
    assert settings.player_count == 5  # Default
    assert settings.role_distribution[Role.MAFIA] == 1
    assert settings.role_distribution[Role.DETECTIVE] == 1
    assert settings.role_distribution[Role.DOCTOR] == 1
    assert settings.role_distribution[Role.VILLAGER] == 2
    assert settings.discussion_time_limit == 300
    assert settings.voting_time_limit == 60
    assert settings.doctor_rules == DoctorRules.STANDARD
    assert settings.reveal_role_on_death is True
    assert settings.debug_mode is False


def test_game_settings_custom_values():
    """Test that GameSettings can be created with custom values."""
    settings = GameSettings(
        player_count=9,
        role_distribution={
            Role.MAFIA: 2,
            Role.DETECTIVE: 1,
            Role.DOCTOR: 1,
            Role.VILLAGER: 5
        },
        discussion_time_limit=600,
        voting_time_limit=120,
        doctor_rules=DoctorRules.NO_SELF_PROTECTION,
        reveal_role_on_death=False,
        debug_mode=True
    )
    
    assert settings.player_count == 9
    assert settings.role_distribution[Role.MAFIA] == 2
    assert settings
    assert settings.discussion_time_limit == 600
    assert settings.voting_time_limit == 120
    assert settings.doctor_rules == DoctorRules.NO_SELF_PROTECTION
    assert settings.reveal_role_on_death is False
    assert settings.debug_mode is True


def test_game_settings_serialization():
    """Test that GameSettings can be serialized to and from JSON."""
    settings = GameSettings(
        player_count=7,
        role_distribution={
            Role.MAFIA: 2,
            Role.DETECTIVE: 1,
            Role.DOCTOR: 1,
            Role.VILLAGER: 3
        },
        doctor_rules=DoctorRules.NO_CONSECUTIVE
    )
    
    # Convert to dict (JSON serializable)
    settings_dict = settings.model_dump()
    
    # Check fields were serialized correctly
    assert isinstance(settings_dict["id"], str)
    assert settings_dict["player_count"] == 7
    assert settings_dict["role_distribution"]["mafia"] == 2
    assert settings_dict["role_distribution"]["detective"] == 1
    assert settings_dict["role_distribution"]["doctor"] == 1
    assert settings_dict["role_distribution"]["villager"] == 3
    assert settings_dict["doctor_rules"] == "no_consecutive"
    
    # Recreate from dict
    recreated_settings = GameSettings(**settings_dict)
    
    # Check fields were deserialized correctly
    assert recreated_settings.id == settings.id
    assert recreated_settings.player_count == 7
    assert recreated_settings.role_distribution[Role.MAFIA] == 2
    assert recreated_settings.role_distribution[Role.DETECTIVE] == 1
    assert recreated_settings.role_distribution[Role.DOCTOR] == 1
    assert recreated_settings.role_distribution[Role.VILLAGER] == 3
    assert recreated_settings.doctor_rules == DoctorRules.NO_CONSECUTIVE


def test_game_settings_validation_role_counts():
    """Test that GameSettings validators work correctly for role counts."""
    # Test missing mafia
    with pytest.raises(ValidationError):
        GameSettings(role_distribution={
            Role.DETECTIVE: 1,
            Role.DOCTOR: 1,
            Role.VILLAGER: 3
        })
    
    # Test missing innocent roles
    with pytest.raises(ValidationError):
        GameSettings(role_distribution={
            Role.MAFIA: 5,
        })


def test_game_settings_auto_adjust_villagers():
    """Test that GameSettings automatically adjusts villager count."""
    # Create settings with player_count=7 but incomplete role distribution
    settings = GameSettings(
        player_count=7,
        role_distribution={
            Role.MAFIA: 2,
            Role.DETECTIVE: 1,
            Role.DOCTOR: 1,
        }
    )
    
    # Villager count should be auto-adjusted to 3
    assert settings.role_distribution[Role.VILLAGER] == 3
    assert sum(settings.role_distribution.values()) == 7


def test_game_settings_min_max_players():
    """Test that GameSettings enforces minimum and maximum player counts."""
    # Test minimum player count (5)
    with pytest.raises(ValidationError):
        GameSettings(player_count=4)
    
    # Test maximum player count (15)
    with pytest.raises(ValidationError):
        GameSettings(player_count=16)
    
    # Test valid minimum
    settings_min = GameSettings(player_count=5)
    assert settings_min.player_count == 5
    
    # Test valid maximum
    settings_max = GameSettings(player_count=15)
    assert settings_max.player_count == 15


def test_game_settings_too_many_special_roles():
    """Test that GameSettings validates special roles vs. player count."""
    # Too many special roles for the player count
    with pytest.raises(ValidationError):
        GameSettings(
            player_count=7,
            role_distribution={
                Role.MAFIA: 3,
                Role.DETECTIVE: 3,
                Role.DOCTOR: 3
            }
        ) 
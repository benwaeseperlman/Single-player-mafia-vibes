import pytest
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import ValidationError

from app.models.memory import PublicMemory, PrivateMemory, AIMemory
from app.models.player import Role
from app.models.game import GamePhase


def test_public_memory_creation():
    """Test that a PublicMemory can be created with default values."""
    memory = PublicMemory()
    
    assert memory.current_day == 0
    assert memory.current_phase == "pregame"
    assert memory.killed_players == []
    assert memory.lynched_players == []
    assert memory.voting_history == {}
    assert memory.statements == []
    assert memory.total_player_count == 0
    assert memory.key_events == []


def test_public_memory_custom_values():
    """Test that a PublicMemory can be created with custom values."""
    player_id1 = uuid4()
    player_id2 = uuid4()
    
    memory = PublicMemory(
        current_day=2,
        current_phase="day",
        killed_players=[
            {"player_id": player_id1, "player_name": "Player 1", "role": "villager", "day_number": 1, "cause": "mafia_kill"}
        ],
        lynched_players=[
            {"player_id": player_id2, "player_name": "Player 2", "role": "mafia", "day_number": 1, "vote_count": 5}
        ],
        voting_history={
            1: {player_id1: player_id2}
        },
        statements=[
            {"player_id": player_id1, "player_name": "Player 1", "day": 1, "message": "I'm suspicious of Player 2"}
        ],
        total_player_count=7,
        key_events=[
            {"day": 1, "event_type": "lynching", "description": "Player 2 was lynched and revealed to be Mafia"}
        ]
    )
    
    assert memory.current_day == 2
    assert memory.current_phase == "day"
    assert len(memory.killed_players) == 1
    assert memory.killed_players[0]["player_name"] == "Player 1"
    assert len(memory.lynched_players) == 1
    assert memory.lynched_players[0]["player_name"] == "Player 2"
    assert memory.lynched_players[0]["role"] == "mafia"
    assert 1 in memory.voting_history
    assert player_id1 in memory.voting_history[1]
    assert memory.voting_history[1][player_id1] == player_id2
    assert len(memory.statements) == 1
    assert memory.statements[0]["message"] == "I'm suspicious of Player 2"
    assert memory.total_player_count == 7
    assert len(memory.key_events) == 1
    assert memory.key_events[0]["event_type"] == "lynching"


def test_private_memory_creation():
    """Test that a PrivateMemory can be created with valid values."""
    player_id1 = uuid4()
    player_id2 = uuid4()
    player_id3 = uuid4()
    
    # Required: own_role
    memory = PrivateMemory(own_role=Role.MAFIA)
    
    assert memory.own_role == Role.MAFIA
    assert memory.known_mafia == []
    assert memory.investigation_results == {}
    assert memory.role_suspicions == {}
    assert memory.recent_actions == []
    assert memory.strategy_notes == []
    assert memory.priority_targets == {}
    assert memory.trust_levels == {}
    
    # With all optional fields
    memory = PrivateMemory(
        own_role=Role.DETECTIVE,
        known_mafia=[player_id1],
        investigation_results={player_id2: True},  # player_id2 is mafia
        role_suspicions={
            player_id3: {
                "mafia": 8,
                "villager": 1,
                "detective": 1,
                "doctor": 0
            }
        },
        recent_actions=[
            {"day": 1, "action_type": "detective_investigate", "target_id": player_id2, "result": True}
        ],
        strategy_notes=["I should investigate Player 3 next"],
        priority_targets={player_id3: 9},
        trust_levels={player_id1: 2, player_id2: 1, player_id3: 3}
    )
    
    assert memory.own_role == Role.DETECTIVE
    assert player_id1 in memory.known_mafia
    assert memory.investigation_results[player_id2] is True
    assert player_id3 in memory.role_suspicions
    assert memory.role_suspicions[player_id3]["mafia"] == 8
    assert len(memory.recent_actions) == 1
    assert memory.recent_actions[0]["target_id"] == player_id2
    assert len(memory.strategy_notes) == 1
    assert memory.priority_targets[player_id3] == 9
    assert memory.trust_levels[player_id1] == 2


def test_ai_memory_creation():
    """Test that an AIMemory can be created with valid values."""
    player_id = uuid4()
    
    # Create with required fields
    memory = AIMemory(
        player_id=player_id,
        private=PrivateMemory(own_role=Role.VILLAGER)
    )
    
    assert isinstance(memory.id, UUID)
    assert memory.player_id == player_id
    assert isinstance(memory.public, PublicMemory)
    assert memory.private.own_role == Role.VILLAGER
    assert isinstance(memory.last_updated, datetime)
    assert memory.memory_capacity == 50  # Default
    
    # Methods should exist
    assert callable(memory.update_memory)
    assert callable(memory.get_memory_context)


def test_ai_memory_get_memory_context():
    """Test that get_memory_context returns the expected structure."""
    player_id = uuid4()
    
    memory = AIMemory(
        player_id=player_id,
        private=PrivateMemory(own_role=Role.MAFIA)
    )
    
    context = memory.get_memory_context()
    
    # Check structure
    assert "public_knowledge" in context
    assert "private_knowledge" in context
    
    # Public knowledge
    assert "current_day" in context["public_knowledge"]
    assert "current_phase" in context["public_knowledge"]
    assert "killed_players" in context["public_knowledge"]
    assert "lynched_players" in context["public_knowledge"]
    assert "key_events" in context["public_knowledge"]
    assert "voting_history" in context["public_knowledge"]
    assert "player_statements" in context["public_knowledge"]
    
    # Private knowledge
    assert "role" in context["private_knowledge"]
    assert context["private_knowledge"]["role"] == Role.MAFIA
    assert "known_mafia" in context["private_knowledge"]
    assert "investigation_results" in context["private_knowledge"]
    assert "suspicions" in context["private_knowledge"]
    assert "recent_actions" in context["private_knowledge"]
    assert "strategy" in context["private_knowledge"]
    assert "priorities" in context["private_knowledge"]
    assert "trust" in context["private_knowledge"]


def test_ai_memory_serialization():
    """Test that AIMemory can be serialized to and from JSON."""
    player_id = uuid4()
    target_id = uuid4()
    
    memory = AIMemory(
        player_id=player_id,
        private=PrivateMemory(
            own_role=Role.DETECTIVE,
            investigation_results={target_id: False}  # Not mafia
        ),
        public=PublicMemory(
            current_day=1,
            current_phase="day",
            key_events=[
                {"day": 1, "event_type": "investigation", "description": "Detective investigated a player"}
            ]
        )
    )
    
    # Convert to dict
    memory_dict = memory.model_dump()
    
    # Check serialization of key fields
    assert memory_dict["player_id"] == str(player_id)
    assert memory_dict["id"] == str(memory.id)
    assert memory_dict["private"]["own_role"] == "detective"
    assert str(target_id) in memory_dict["private"]["investigation_results"]
    assert memory_dict["private"]["investigation_results"][str(target_id)] is False
    assert memory_dict["public"]["current_day"] == 1
    assert memory_dict["public"]["current_phase"] == "day"
    assert len(memory_dict["public"]["key_events"]) == 1
    
    # Recreate from dict
    recreated_memory = AIMemory(**memory_dict)
    
    # Check deserialization
    assert recreated_memory.id == memory.id
    assert recreated_memory.player_id == player_id
    assert recreated_memory.private.own_role == Role.DETECTIVE
    assert recreated_memory.private.investigation_results == {target_id: False}
    assert recreated_memory.public.current_day == 1
    assert recreated_memory.public.current_phase == GamePhase.DAY


def test_memory_validation():
    """Test that memory validation works as expected."""
    player_id = uuid4()
    
    # Missing required field (private is required for AIMemory)
    with pytest.raises(ValidationError):
        AIMemory(
            player_id=player_id
            # Missing private
        )
    
    # Missing required field (own_role is required for PrivateMemory)
    with pytest.raises(ValidationError):
        PrivateMemory()  # Missing own_role
    
    # Invalid value for own_role
    with pytest.raises(ValidationError):
        PrivateMemory(own_role="invalid_role")
    
    # Invalid enum for current_phase
    with pytest.raises(ValidationError):
        PublicMemory(current_phase="invalid_phase") 
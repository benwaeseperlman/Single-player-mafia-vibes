import pytest
from uuid import uuid4
from datetime import datetime
from pydantic import ValidationError

from app.models.actions import (
    ActionType, BaseAction, MafiaKillAction, 
    DetectiveInvestigateAction, DoctorProtectAction, 
    VoteAction, ChatMessage
)


def test_action_type_enum():
    """Test that ActionType enum contains the expected values."""
    assert ActionType.MAFIA_KILL.value == "mafia_kill"
    assert ActionType.DETECTIVE_INVESTIGATE.value == "detective_investigate"
    assert ActionType.DOCTOR_PROTECT.value == "doctor_protect"
    assert ActionType.VOTE.value == "vote"
    assert ActionType.CHAT_MESSAGE.value == "chat_message"
    
    # Test enum conversion from string
    assert ActionType("mafia_kill") == ActionType.MAFIA_KILL
    assert ActionType("detective_investigate") == ActionType.DETECTIVE_INVESTIGATE
    assert ActionType("doctor_protect") == ActionType.DOCTOR_PROTECT
    assert ActionType("vote") == ActionType.VOTE
    assert ActionType("chat_message") == ActionType.CHAT_MESSAGE


def test_base_action_creation():
    """Test that a BaseAction can be created with valid data."""
    player_id = uuid4()
    target_id = uuid4()
    
    action = BaseAction(
        action_type=ActionType.VOTE,
        player_id=player_id,
        target_id=target_id
    )
    
    assert action.action_type == ActionType.VOTE
    assert action.player_id == player_id
    assert action.target_id == target_id
    assert isinstance(action.timestamp, datetime)


def test_mafia_kill_action():
    """Test that a MafiaKillAction can be created with valid data."""
    player_id = uuid4()
    target_id = uuid4()
    
    action = MafiaKillAction(
        player_id=player_id,
        target_id=target_id
    )
    
    assert action.action_type == ActionType.MAFIA_KILL
    assert action.player_id == player_id
    assert action.target_id == target_id
    assert isinstance(action.timestamp, datetime)


def test_detective_investigate_action():
    """Test that a DetectiveInvestigateAction can be created with valid data."""
    player_id = uuid4()
    target_id = uuid4()
    
    # Without result
    action = DetectiveInvestigateAction(
        player_id=player_id,
        target_id=target_id
    )
    
    assert action.action_type == ActionType.DETECTIVE_INVESTIGATE
    assert action.player_id == player_id
    assert action.target_id == target_id
    assert action.result is None
    
    # With result
    action = DetectiveInvestigateAction(
        player_id=player_id,
        target_id=target_id,
        result=True  # Target is Mafia
    )
    
    assert action.result is True


def test_doctor_protect_action():
    """Test that a DoctorProtectAction can be created with valid data."""
    player_id = uuid4()
    target_id = uuid4()
    
    action = DoctorProtectAction(
        player_id=player_id,
        target_id=target_id
    )
    
    assert action.action_type == ActionType.DOCTOR_PROTECT
    assert action.player_id == player_id
    assert action.target_id == target_id


def test_vote_action():
    """Test that a VoteAction can be created with valid data."""
    player_id = uuid4()
    target_id = uuid4()
    
    action = VoteAction(
        player_id=player_id,
        target_id=target_id
    )
    
    assert action.action_type == ActionType.VOTE
    assert action.player_id == player_id
    assert action.target_id == target_id


def test_chat_message():
    """Test that a ChatMessage can be created with valid data."""
    player_id = uuid4()
    
    message = ChatMessage(
        player_id=player_id,
        message="Hello, world!"
    )
    
    assert message.action_type == ActionType.CHAT_MESSAGE
    assert message.player_id == player_id
    assert message.message == "Hello, world!"
    assert message.is_public is True
    
    # Private message
    private_message = ChatMessage(
        player_id=player_id,
        message="This is a private message",
        is_public=False
    )
    
    assert private_message.is_public is False


def test_action_serialization():
    """Test that actions can be serialized to and from JSON."""
    player_id = uuid4()
    target_id = uuid4()
    timestamp = datetime.now()
    
    # MafiaKillAction
    mafia_action = MafiaKillAction(
        player_id=player_id,
        target_id=target_id,
        timestamp=timestamp
    )
    
    # Convert to dict
    mafia_dict = mafia_action.model_dump()
    
    # Check serialization
    assert mafia_dict["action_type"] == "mafia_kill"
    assert str(mafia_dict["player_id"]) == str(player_id)
    assert str(mafia_dict["target_id"]) == str(target_id)
    
    # Recreate from dict
    recreated_action = MafiaKillAction(**mafia_dict)
    
    assert recreated_action.action_type == ActionType.MAFIA_KILL
    assert recreated_action.player_id == player_id
    assert recreated_action.target_id == target_id
    assert recreated_action.timestamp == timestamp


def test_action_validation():
    """Test that action validation works as expected."""
    player_id = uuid4()
    target_id = uuid4()
    
    # Invalid action type
    with pytest.raises(ValidationError):
        BaseAction(
            action_type="invalid_action",
            player_id=player_id,
            target_id=target_id
        )
    
    # Missing required field
    with pytest.raises(ValidationError):
        MafiaKillAction(
            player_id=player_id,
            # Missing target_id
        )
    
    # Invalid UUID
    with pytest.raises(ValidationError):
        MafiaKillAction(
            player_id="not-a-uuid",
            target_id=target_id
        )
    
    # Empty message
    with pytest.raises(ValidationError):
        ChatMessage(
            player_id=player_id,
            message=""  # Empty message
        )
    
    # Valid message
    message = ChatMessage(
        player_id=player_id,
        message="Valid message"
    )
    assert message.message == "Valid message" 
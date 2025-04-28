from pydantic import BaseModel, Field, field_validator, ConfigDict
from uuid import UUID
from enum import Enum
from typing import Optional
from datetime import datetime


class ActionType(str, Enum):
    """Types of actions players can take."""
    MAFIA_KILL = "mafia_kill"
    DETECTIVE_INVESTIGATE = "detective_investigate"
    DOCTOR_PROTECT = "doctor_protect"
    VOTE = "vote"
    CHAT_MESSAGE = "chat_message"


class BaseAction(BaseModel):
    """Base model for all player actions."""
    action_type: ActionType
    player_id: UUID  # ID of the player performing the action
    target_id: UUID  # ID of the target player
    timestamp: datetime = Field(default_factory=datetime.now)


class MafiaKillAction(BaseAction):
    """Mafia night action to kill a player."""
    action_type: ActionType = ActionType.MAFIA_KILL
    
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "player_id": "123e4567-e89b-12d3-a456-426614174000",
                "target_id": "123e4567-e89b-12d3-a456-426614174001",
                "timestamp": "2025-04-27T23:30:00"
            }
        }
    )


class DetectiveInvestigateAction(BaseAction):
    """Detective night action to investigate a player."""
    action_type: ActionType = ActionType.DETECTIVE_INVESTIGATE
    result: Optional[bool] = None  # True if target is Mafia, False if innocent
    
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "player_id": "123e4567-e89b-12d3-a456-426614174000",
                "target_id": "123e4567-e89b-12d3-a456-426614174001",
                "timestamp": "2025-04-27T23:30:00",
                "result": None
            }
        }
    )


class DoctorProtectAction(BaseAction):
    """Doctor night action to protect a player."""
    action_type: ActionType = ActionType.DOCTOR_PROTECT
    
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "player_id": "123e4567-e89b-12d3-a456-426614174000",
                "target_id": "123e4567-e89b-12d3-a456-426614174001",
                "timestamp": "2025-04-27T23:30:00"
            }
        }
    )


class VoteAction(BaseAction):
    """Player vote during day phase to lynch another player."""
    action_type: ActionType = ActionType.VOTE
    
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "player_id": "123e4567-e89b-12d3-a456-426614174000",
                "target_id": "123e4567-e89b-12d3-a456-426614174001",
                "timestamp": "2025-04-27T12:30:00"
            }
        }
    )


class ChatMessage(BaseModel):
    """Chat message sent by a player during the day phase."""
    action_type: ActionType = ActionType.CHAT_MESSAGE
    player_id: UUID
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)
    is_public: bool = True  # Whether the message is visible to all players

    @field_validator('message')
    @classmethod
    def message_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('message must not be empty')
        return v

    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "player_id": "123e4567-e89b-12d3-a456-426614174000",
                "message": "I think Player 3 is acting suspicious.",
                "timestamp": "2025-04-27T12:15:00",
                "is_public": True
            }
        }
    ) 
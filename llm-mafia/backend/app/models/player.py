from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID, uuid4
from typing import Optional


class Role(str, Enum):
    """Enum for player roles in the Mafia game."""
    MAFIA = "mafia"
    DETECTIVE = "detective"
    DOCTOR = "doctor"
    VILLAGER = "villager"


class PlayerStatus(str, Enum):
    """Enum for player status in the Mafia game."""
    ALIVE = "alive"
    DEAD = "dead"


class Player(BaseModel):
    """Pydantic model for a player in the Mafia game."""
    id: UUID = Field(default_factory=uuid4)
    name: str
    role: Role
    status: PlayerStatus = PlayerStatus.ALIVE
    is_human: bool = False
    persona_id: Optional[UUID] = None  # Reference to an AIPersona for AI players

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Player 1",
                "role": "villager",
                "status": "alive",
                "is_human": True,
                "persona_id": None
            }
        }
    ) 
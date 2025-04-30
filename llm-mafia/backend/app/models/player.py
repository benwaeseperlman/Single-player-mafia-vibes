from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, field_validator, UUID4
from uuid import UUID, uuid4
from typing import Optional, List, Dict


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
    id: UUID4 = Field(default_factory=uuid4)
    name: str
    role: Role
    status: PlayerStatus = PlayerStatus.ALIVE
    is_human: bool = False
    persona_id: Optional[UUID4] = None  # Reference to an AIPersona for AI players
    is_saved: bool = False  # Tracks if Doctor saved this player tonight
    investigation_result: Optional[str] = None  # Stores Detective's findings privately

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "name": "Alice",
                    "role": "villager",
                    "status": "alive",
                    "is_human": True,
                    "persona_id": None
                }
            ]
        }
    ) 
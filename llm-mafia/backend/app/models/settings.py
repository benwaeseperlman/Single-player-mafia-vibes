from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict, model_serializer
from uuid import UUID, uuid4
from typing import Dict, Optional, ClassVar, Any
from enum import Enum

from .player import Role


class DoctorRules(str, Enum):
    """Rules for the Doctor role."""
    STANDARD = "standard"  # Can protect anyone including self
    NO_SELF_PROTECTION = "no_self_protection"  # Cannot protect self
    NO_CONSECUTIVE = "no_consecutive"  # Cannot protect the same player on consecutive nights


class GameSettings(BaseModel):
    """Game settings configuration."""
    id: UUID = Field(default_factory=uuid4)
    player_count: int = Field(ge=5, le=15)  # Min 5, max 15 players
    
    # Role distribution: how many of each role
    role_distribution: Dict[Role, int] = {
        Role.MAFIA: 1,
        Role.DETECTIVE: 1,
        Role.DOCTOR: 1,
        Role.VILLAGER: 2,  # Minimum player count is 5 (1 human + 4 AI)
    }
    
    # Time limits (in seconds, 0 = no limit)
    discussion_time_limit: int = 300  # 5 minutes for discussion phase
    voting_time_limit: int = 60  # 1 minute for voting phase
    
    # Game rule variants
    doctor_rules: DoctorRules = DoctorRules.STANDARD
    reveal_role_on_death: bool = True  # Whether to reveal a player's role when they die
    
    # Custom settings for testing/development
    debug_mode: bool = False  # Enables additional logging and might reveal hidden info
    
    @field_validator('role_distribution')
    def validate_role_counts(cls, role_distribution):
        """Validate that role distribution makes sense for the game."""
        # Must have at least one mafia
        if role_distribution.get(Role.MAFIA, 0) < 1:
            raise ValueError("Game must have at least one Mafia member")
        
        # Must have at least one innocent (villager, detective, or doctor)
        innocent_count = (
            role_distribution.get(Role.VILLAGER, 0) +
            role_distribution.get(Role.DETECTIVE, 0) +
            role_distribution.get(Role.DOCTOR, 0)
        )
        if innocent_count < 1:
            raise ValueError("Game must have at least one innocent role")
        
        return role_distribution
    
    @model_validator(mode='after')
    def validate_total_players(self) -> 'GameSettings':
        """Validate that role distribution matches player count."""
        player_count = self.player_count
        role_distribution = self.role_distribution
        
        total_roles = sum(role_distribution.values())
        
        if total_roles != player_count:
            # Auto-adjust the number of villagers to match player count
            villager_count = player_count - (total_roles - role_distribution.get(Role.VILLAGER, 0))
            if villager_count < 0:
                raise ValueError(f"Too many special roles for player count of {player_count}")
            
            role_distribution[Role.VILLAGER] = villager_count
            self.role_distribution = role_distribution
        
        return self
    
    @model_serializer
    def serialize_model(self) -> dict:
        return {
            "id": str(self.id),
            "player_count": self.player_count,
            "role_distribution": {role.value: count for role, count in self.role_distribution.items()},
            "discussion_time_limit": self.discussion_time_limit,
            "voting_time_limit": self.voting_time_limit,
            "doctor_rules": self.doctor_rules.value,
            "reveal_role_on_death": self.reveal_role_on_death,
            "debug_mode": self.debug_mode
        }
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174001",
                "player_count": 7,
                "role_distribution": {
                    "mafia": 2,
                    "detective": 1,
                    "doctor": 1,
                    "villager": 3
                },
                "discussion_time_limit": 300,
                "voting_time_limit": 60,
                "doctor_rules": "standard",
                "reveal_role_on_death": True,
                "debug_mode": False
            }
        }
    ) 
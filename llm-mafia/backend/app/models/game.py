from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, model_serializer
from uuid import UUID, uuid4
from typing import List, Dict, Optional, Any
from datetime import datetime

from .player import Player


class GamePhase(str, Enum):
    """Game phases for the Mafia game."""
    PREGAME = "pregame"  # Setup phase before the game starts
    NIGHT = "night"      # Night phase where special roles perform actions
    DAY = "day"          # Day phase with discussion
    VOTING = "voting"    # Voting phase where players select someone to lynch
    GAMEOVER = "gameover"  # Game has ended


class GameState(BaseModel):
    """Main game state model for the Mafia game."""
    game_id: UUID = Field(default_factory=uuid4)
    players: List[Player] = []
    phase: GamePhase = GamePhase.PREGAME
    day_number: int = Field(default=0, ge=0)  # 0 during pregame, 1 for first day, etc.
    
    # References to other models that will be defined later
    settings_id: Optional[UUID] = None  # Reference to GameSettings
    
    # History of game events
    history: List[str] = []
    
    # Track night actions and votes
    night_actions: Dict[UUID, Any] = {}  # Player ID -> Action
    votes: Dict[UUID, UUID] = {}  # Voter ID -> Target ID
    
    # Timestamps for tracking
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Outcome if game is over
    winner: Optional[str] = None  # "mafia" or "innocents"

    def add_to_history(self, event: str) -> None:
        """Add an event to the game history."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.history.append(f"[{timestamp}] {event}")
        self.updated_at = datetime.now()
    
    @model_serializer
    def serialize_model(self) -> dict:
        return {
            "game_id": str(self.game_id),
            "players": [player.model_dump() for player in self.players],
            "phase": self.phase.value,
            "day_number": self.day_number,
            "settings_id": str(self.settings_id) if self.settings_id else None,
            "history": self.history,
            "night_actions": {str(k): v for k, v in self.night_actions.items()},
            "votes": {str(k): str(v) for k, v in self.votes.items()},
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "winner": self.winner
        }
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "game_id": "123e4567-e89b-12d3-a456-426614174000",
                "players": [],
                "phase": "pregame",
                "day_number": 0,
                "settings_id": "123e4567-e89b-12d3-a456-426614174001",
                "history": ["Game created"],
                "night_actions": {},
                "votes": {},
                "created_at": "2025-04-27T12:00:00",
                "updated_at": "2025-04-27T12:00:00",
                "winner": None
            }
        }
    ) 
from pydantic import BaseModel, Field, ConfigDict, model_serializer
from uuid import UUID, uuid4
from typing import Dict, List, Set, Any, Optional
from datetime import datetime

from .player import Role
from .game import GamePhase  # Import GamePhase


class PublicMemory(BaseModel):
    """Public information that all players can remember from the game."""
    # Day and phase tracking
    current_day: int = 0
    current_phase: GamePhase = GamePhase.PREGAME  # Use GamePhase enum
    
    # Deaths and lynches
    killed_players: List[Dict[str, Any]] = []  # List of {player_id, player_name, role, day_number, cause}
    lynched_players: List[Dict[str, Any]] = []  # List of {player_id, player_name, role, day_number, vote_count}
    
    # Voting history by day and player
    voting_history: Dict[int, Dict[UUID, UUID]] = {}  # {day_number: {voter_id: target_id}}
    
    # Public statements made by players
    statements: List[Dict[str, Any]] = []  # List of {player_id, player_name, day, message}
    
    # Game rules
    total_player_count: int = 0  # Total number of players at game start
    
    # Notable public events
    key_events: List[Dict[str, Any]] = []  # List of {day, event_type, description}
    
    @model_serializer
    def serialize_model(self) -> dict:
        return {
            "current_day": self.current_day,
            "current_phase": self.current_phase.value,
            "killed_players": self.killed_players,
            "lynched_players": self.lynched_players,
            "voting_history": {
                day: {str(voter): str(target) for voter, target in votes.items()}
                for day, votes in self.voting_history.items()
            },
            "statements": self.statements,
            "total_player_count": self.total_player_count,
            "key_events": self.key_events
        }


class PrivateMemory(BaseModel):
    """Private information that an AI remembers but shouldn't share publicly."""
    # Role-specific knowledge
    own_role: Role  # The AI's own role
    
    # For Mafia, who the other Mafia members are
    known_mafia: List[UUID] = []  # List of player IDs known to be Mafia (if AI is Mafia)
    
    # For Detective, results of investigations
    investigation_results: Dict[UUID, bool] = {}  # {player_id: is_mafia}
    
    # Suspicions and beliefs (confidence level 0-10)
    role_suspicions: Dict[UUID, Dict[Role, int]] = {}  # {player_id: {role: confidence}}
    
    # Recent actions by the AI
    recent_actions: List[Dict[str, Any]] = []  # List of {day, action_type, target_id, result}
    
    # Strategy and planning
    strategy_notes: List[str] = []  # AI's internal strategic thoughts
    
    # Targeted players that the AI is focusing on
    priority_targets: Dict[UUID, int] = {}  # {player_id: priority_level}
    
    # Trust levels towards other players (0-10)
    trust_levels: Dict[UUID, int] = {}  # {player_id: trust_level}
    
    @model_serializer
    def serialize_model(self) -> dict:
        return {
            "own_role": self.own_role.value,
            "known_mafia": [str(id) for id in self.known_mafia],
            "investigation_results": {str(k): v for k, v in self.investigation_results.items()},
            "role_suspicions": {
                str(player_id): {role.value: conf for role, conf in suspicions.items()}
                for player_id, suspicions in self.role_suspicions.items()
            },
            "recent_actions": [
                {**action, "target_id": str(action["target_id"]) if "target_id" in action else None}
                for action in self.recent_actions
            ],
            "strategy_notes": self.strategy_notes,
            "priority_targets": {str(k): v for k, v in self.priority_targets.items()},
            "trust_levels": {str(k): v for k, v in self.trust_levels.items()}
        }


class AIMemory(BaseModel):
    """Memory model for an AI agent in the Mafia game."""
    id: UUID = Field(default_factory=uuid4)
    player_id: UUID  # ID of the AI player this memory belongs to
    public: PublicMemory = Field(default_factory=PublicMemory)
    private: PrivateMemory
    last_updated: datetime = Field(default_factory=datetime.now)
    
    # Memory decay - older less important memories may get summarized or forgotten
    memory_capacity: int = 50  # Number of detailed individual memories to retain
    
    def update_memory(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Update the AI's memory with a new event."""
        self.last_updated = datetime.now()
        
        # Implementation would handle different event types and update appropriate memory sections
        # This is a placeholder for the actual implementation
        pass
    
    def get_memory_context(self) -> Dict[str, Any]:
        """Get formatted memory context for LLM prompt."""
        # This would format the memory in a way that's suitable for inclusion in an LLM prompt
        # This is a placeholder for the actual implementation
        return {
            "public_knowledge": {
                "current_day": self.public.current_day,
                "current_phase": self.public.current_phase,
                "killed_players": self.public.killed_players,
                "lynched_players": self.public.lynched_players,
                "key_events": self.public.key_events,
                "voting_history": self.public.voting_history,
                "player_statements": self.public.statements[-min(self.memory_capacity, len(self.public.statements)):]
            },
            "private_knowledge": {
                "role": self.private.own_role,
                "known_mafia": self.private.known_mafia,
                "investigation_results": self.private.investigation_results,
                "suspicions": self.private.role_suspicions,
                "recent_actions": self.private.recent_actions,
                "strategy": self.private.strategy_notes,
                "priorities": self.private.priority_targets,
                "trust": self.private.trust_levels
            }
        }
    
    @model_serializer
    def serialize_model(self) -> dict:
        return {
            "id": str(self.id),
            "player_id": str(self.player_id),
            "public": self.public.model_dump(),
            "private": self.private.model_dump(),
            "last_updated": self.last_updated.isoformat(),
            "memory_capacity": self.memory_capacity
        }
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174004",
                "player_id": "123e4567-e89b-12d3-a456-426614174000",
                "public": {
                    "current_day": 2,
                    "current_phase": "day",
                    "killed_players": [
                        {"player_id": "123e4567-e89b-12d3-a456-426614174001", "player_name": "Player 2", "role": "villager", "day_number": 1, "cause": "mafia_kill"}
                    ],
                    "lynched_players": [
                        {"player_id": "123e4567-e89b-12d3-a456-426614174005", "player_name": "Player 6", "role": "villager", "day_number": 1, "vote_count": 4}
                    ],
                    "voting_history": {
                        "1": {
                            "123e4567-e89b-12d3-a456-426614174000": "123e4567-e89b-12d3-a456-426614174005"
                        }
                    },
                    "statements": [
                        {"player_id": "123e4567-e89b-12d3-a456-426614174003", "player_name": "Player 4", "day": 1, "message": "I'm suspicious of Player 6"}
                    ],
                    "total_player_count": 7,
                    "key_events": [
                        {"day": 1, "event_type": "lynching", "description": "Player 6 was lynched and revealed to be Villager"}
                    ]
                },
                "private": {
                    "own_role": "detective",
                    "known_mafia": [],
                    "investigation_results": {
                        "123e4567-e89b-12d3-a456-426614174002": False
                    },
                    "role_suspicions": {
                        "123e4567-e89b-12d3-a456-426614174003": {
                            "mafia": 7, 
                            "villager": 2,
                            "detective": 0,
                            "doctor": 1
                        }
                    },
                    "recent_actions": [
                        {"day": 1, "action_type": "detective_investigate", "target_id": "123e4567-e89b-12d3-a456-426614174002", "result": False}
                    ],
                    "strategy_notes": [
                        "Player 3 is acting suspicious, might be Mafia"
                    ],
                    "priority_targets": {
                        "123e4567-e89b-12d3-a456-426614174003": 8
                    },
                    "trust_levels": {
                        "123e4567-e89b-12d3-a456-426614174002": 7,
                        "123e4567-e89b-12d3-a456-426614174003": 2
                    }
                },
                "last_updated": "2025-04-28T08:30:00",
                "memory_capacity": 50
            }
        }
    ) 
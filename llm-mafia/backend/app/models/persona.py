from pydantic import BaseModel, Field, ConfigDict, model_serializer
from uuid import UUID, uuid4
from typing import Dict, List, Optional
from enum import Enum


class PersonalityTrait(str, Enum):
    """Common personality traits for AI players."""
    AGGRESSIVE = "aggressive"  # More likely to accuse others and be direct
    LOGICAL = "logical"        # Makes decisions based on observed behavior and logical deduction
    PARANOID = "paranoid"      # Suspicious of everyone, prone to random accusations
    DEFENSIVE = "defensive"    # Likely to defend self and others
    QUIET = "quiet"            # Less talkative, observes more
    TALKATIVE = "talkative"    # Speaks frequently, sometimes with less substance
    DECEPTIVE = "deceptive"    # Good at lying, especially as Mafia
    HONEST = "honest"          # Tends to be straightforward, bad at bluffing
    ANALYTICAL = "analytical"  # Focuses on patterns and voting history
    IMPULSIVE = "impulsive"    # Makes quick decisions without much consideration


class AIPersonaTemplate(BaseModel):
    """Template for AI personas with name and traits."""
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str
    primary_traits: List[PersonalityTrait]  # Main personality characteristics
    
    # Gameplay tendencies on a scale of 0-10
    tendencies: Dict[str, int] = {
        "accusation_likelihood": 5,     # How likely to accuse others (0=never, 10=always)
        "self_preservation": 5,         # How focused on self-preservation (0=selfless, 10=selfish)
        "consistency": 5,               # How consistent in behavior (0=erratic, 10=very consistent)
        "risk_taking": 5,               # Willingness to take risks (0=cautious, 10=reckless)
        "analytical_depth": 5,          # Depth of analysis in discussions (0=surface, 10=deep)
        "emotional_expression": 5,      # Level of emotional expression (0=stoic, 10=emotional)
    }
    
    # Speech style characteristics
    speech_style: Dict[str, str] = {
        "vocabulary": "standard",       # simple, standard, advanced
        "tone": "neutral",              # friendly, neutral, aggressive
        "structure": "clear",           # fragmented, clear, elaborate
        "quirks": ""                    # Any unique speaking patterns or catchphrases
    }
    
    @model_serializer
    def serialize_model(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "primary_traits": [trait.value for trait in self.primary_traits],
            "tendencies": self.tendencies,
            "speech_style": self.speech_style
        }
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174002",
                "name": "Detective Dan",
                "description": "A logical and analytical personality who carefully observes others",
                "primary_traits": ["logical", "analytical", "quiet"],
                "tendencies": {
                    "accusation_likelihood": 3,
                    "self_preservation": 4,
                    "consistency": 8,
                    "risk_taking": 2,
                    "analytical_depth": 9,
                    "emotional_expression": 2
                },
                "speech_style": {
                    "vocabulary": "advanced",
                    "tone": "neutral",
                    "structure": "clear",
                    "quirks": "Often uses detective-themed metaphors"
                }
            }
        }
    )


class AIPersona(AIPersonaTemplate):
    """Instance of an AI persona used in a specific game with additional game-specific data."""
    # Additional fields for game-specific behavior
    role_specific_behavior: Optional[Dict[str, int]] = None  # e.g., detective_investigation_strategy
    
    # The original template this persona is based on, if any
    template_id: Optional[UUID] = None
    
    @model_serializer
    def serialize_model(self) -> dict:
        base_dict = super().serialize_model()
        base_dict.update({
            "role_specific_behavior": self.role_specific_behavior,
            "template_id": str(self.template_id) if self.template_id else None
        })
        return base_dict
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174003",
                "name": "Detective Dan",
                "description": "A logical and analytical personality who carefully observes others",
                "primary_traits": ["logical", "analytical", "quiet"],
                "tendencies": {
                    "accusation_likelihood": 3,
                    "self_preservation": 4,
                    "consistency": 8,
                    "risk_taking": 2,
                    "analytical_depth": 9,
                    "emotional_expression": 2
                },
                "speech_style": {
                    "vocabulary": "advanced",
                    "tone": "neutral",
                    "structure": "clear",
                    "quirks": "Often uses detective-themed metaphors"
                },
                "role_specific_behavior": {
                    "detective_investigation_priority": 8,
                    "mafia_deception_skill": 5
                },
                "template_id": "123e4567-e89b-12d3-a456-426614174002"
            }
        }
    ) 
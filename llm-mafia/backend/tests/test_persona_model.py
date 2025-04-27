import pytest
from uuid import UUID, uuid4
from pydantic import ValidationError

from app.models.persona import PersonalityTrait, AIPersonaTemplate, AIPersona


def test_personality_trait_enum():
    """Test that PersonalityTrait enum contains the expected values."""
    assert PersonalityTrait.AGGRESSIVE.value == "aggressive"
    assert PersonalityTrait.LOGICAL.value == "logical"
    assert PersonalityTrait.PARANOID.value == "paranoid"
    assert PersonalityTrait.DEFENSIVE.value == "defensive"
    assert PersonalityTrait.QUIET.value == "quiet"
    assert PersonalityTrait.TALKATIVE.value == "talkative"
    assert PersonalityTrait.DECEPTIVE.value == "deceptive"
    assert PersonalityTrait.HONEST.value == "honest"
    assert PersonalityTrait.ANALYTICAL.value == "analytical"
    assert PersonalityTrait.IMPULSIVE.value == "impulsive"
    
    # Test enum conversion from string
    assert PersonalityTrait("aggressive") == PersonalityTrait.AGGRESSIVE
    assert PersonalityTrait("logical") == PersonalityTrait.LOGICAL
    assert PersonalityTrait("paranoid") == PersonalityTrait.PARANOID


def test_ai_persona_template_creation():
    """Test that an AIPersonaTemplate can be created with valid data."""
    template = AIPersonaTemplate(
        name="Logical Detective",
        description="A logical and analytical player who carefully observes",
        primary_traits=[PersonalityTrait.LOGICAL, PersonalityTrait.ANALYTICAL, PersonalityTrait.QUIET]
    )
    
    assert isinstance(template.id, UUID)
    assert template.name == "Logical Detective"
    assert template.description == "A logical and analytical player who carefully observes"
    assert PersonalityTrait.LOGICAL in template.primary_traits
    assert PersonalityTrait.ANALYTICAL in template.primary_traits
    assert PersonalityTrait.QUIET in template.primary_traits
    
    # Check default tendencies and speech_style
    assert template.tendencies["accusation_likelihood"] == 5
    assert template.tendencies["self_preservation"] == 5
    assert template.tendencies["consistency"] == 5
    assert template.tendencies["risk_taking"] == 5
    assert template.tendencies["analytical_depth"] == 5
    assert template.tendencies["emotional_expression"] == 5
    
    assert template.speech_style["vocabulary"] == "standard"
    assert template.speech_style["tone"] == "neutral"
    assert template.speech_style["structure"] == "clear"
    assert template.speech_style["quirks"] == ""


def test_ai_persona_template_custom_values():
    """Test that an AIPersonaTemplate can be created with custom tendencies and speech style."""
    template = AIPersonaTemplate(
        name="Paranoid Accuser",
        description="A paranoid player who frequently accuses others",
        primary_traits=[PersonalityTrait.PARANOID, PersonalityTrait.AGGRESSIVE, PersonalityTrait.TALKATIVE],
        tendencies={
            "accusation_likelihood": 9,
            "self_preservation": 8,
            "consistency": 3,
            "risk_taking": 7,
            "analytical_depth": 2,
            "emotional_expression": 8
        },
        speech_style={
            "vocabulary": "simple",
            "tone": "aggressive",
            "structure": "fragmented",
            "quirks": "Always ends sentences with '... right?'"
        }
    )
    
    assert template.tendencies["accusation_likelihood"] == 9
    assert template.tendencies["self_preservation"] == 8
    assert template.tendencies["consistency"] == 3
    assert template.tendencies["risk_taking"] == 7
    assert template.tendencies["analytical_depth"] == 2
    assert template.tendencies["emotional_expression"] == 8
    
    assert template.speech_style["vocabulary"] == "simple"
    assert template.speech_style["tone"] == "aggressive"
    assert template.speech_style["structure"] == "fragmented"
    assert template.speech_style["quirks"] == "Always ends sentences with '... right?'"


def test_ai_persona_creation():
    """Test that an AIPersona can be created with valid data."""
    template_id = uuid4()
    
    persona = AIPersona(
        name="Smart Detective",
        description="A logical and analytical detective",
        primary_traits=[PersonalityTrait.LOGICAL, PersonalityTrait.ANALYTICAL],
        template_id=template_id,
        role_specific_behavior={
            "detective_investigation_priority": 8,
            "mafia_deception_skill": 5
        }
    )
    
    assert isinstance(persona.id, UUID)
    assert persona.name == "Smart Detective"
    assert persona.description == "A logical and analytical detective"
    assert PersonalityTrait.LOGICAL in persona.primary_traits
    assert PersonalityTrait.ANALYTICAL in persona.primary_traits
    assert persona.template_id == template_id
    assert persona.role_specific_behavior["detective_investigation_priority"] == 8
    assert persona.role_specific_behavior["mafia_deception_skill"] == 5


def test_persona_serialization():
    """Test that AIPersona can be serialized to and from JSON."""
    persona = AIPersona(
        name="Deceptive Mafia",
        description="A highly deceptive mafia member",
        primary_traits=[PersonalityTrait.DECEPTIVE, PersonalityTrait.LOGICAL],
        tendencies={
            "accusation_likelihood": 7,
            "self_preservation": 9,
            "consistency": 6,
            "risk_taking": 4,
            "analytical_depth": 7,
            "emotional_expression": 3
        },
        role_specific_behavior={
            "mafia_deception_skill": 9
        }
    )
    
    # Convert to dict
    persona_dict = persona.model_dump()
    
    # Check serialization
    assert isinstance(persona_dict["id"], str)
    assert persona_dict["name"] == "Deceptive Mafia"
    assert persona_dict["description"] == "A highly deceptive mafia member"
    assert "deceptive" in persona_dict["primary_traits"]
    assert "logical" in persona_dict["primary_traits"]
    assert persona_dict["tendencies"]["accusation_likelihood"] == 7
    assert persona_dict["role_specific_behavior"]["mafia_deception_skill"] == 9
    
    # Recreate from dict
    recreated_persona = AIPersona(**persona_dict)
    
    # Check deserialization
    assert recreated_persona.id == persona.id
    assert recreated_persona.name == persona.name
    assert recreated_persona.primary_traits == persona.primary_traits
    assert recreated_persona.tendencies == persona.tendencies
    assert recreated_persona.role_specific_behavior == persona.role_specific_behavior


def test_persona_validation():
    """Test that AIPersona validation works as expected."""
    # Missing required fields
    with pytest.raises(ValidationError):
        AIPersonaTemplate(
            description="Missing name",
            primary_traits=[PersonalityTrait.LOGICAL]
        )
    
    with pytest.raises(ValidationError):
        AIPersonaTemplate(
            name="Missing description",
            primary_traits=[PersonalityTrait.LOGICAL]
        )
    
    with pytest.raises(ValidationError):
        AIPersonaTemplate(
            name="Missing traits",
            description="A personality"
            # Missing primary_traits
        )
    
    # Invalid trait
    with pytest.raises(ValidationError):
        AIPersonaTemplate(
            name="Invalid trait",
            description="A personality",
            primary_traits=["invalid_trait"]
        ) 
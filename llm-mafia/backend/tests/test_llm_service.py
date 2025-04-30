import pytest
from unittest.mock import patch, MagicMock
import json
from uuid import uuid4

from app.services.llm_service import LLMService, LLMServiceError, llm_service as global_llm_service
from app.models.game import GameState, GamePhase
from app.models.player import Player, Role, PlayerStatus
from app.models.actions import MafiaKillAction, DoctorProtectAction, DetectiveInvestigateAction
from app.core.config import settings, LLMProvider

# Fixture for a basic game state
@pytest.fixture
def game_state_night() -> GameState:
    p1 = Player(id=str(uuid4()), name="AI Mafia", role=Role.MAFIA, is_human=False)
    p2 = Player(id=str(uuid4()), name="AI Doctor", role=Role.DOCTOR, is_human=False)
    p3 = Player(id=str(uuid4()), name="AI Detective", role=Role.DETECTIVE, is_human=False)
    p4 = Player(id=str(uuid4()), name="AI Villager", role=Role.VILLAGER, is_human=False)
    p5 = Player(id=str(uuid4()), name="Human Villager", role=Role.VILLAGER, is_human=True)
    p6 = Player(id=str(uuid4()), name="Dead Player", role=Role.VILLAGER, status=PlayerStatus.DEAD, is_human=False)
    
    state = GameState(
        game_id=uuid4(),
        players=[p1, p2, p3, p4, p5, p6],
        phase=GamePhase.NIGHT,
        day_number=1,
        history=["Game started."],
        settings_id=uuid4()
    )
    return state

# Fixture for an LLMService instance with mocked client
@pytest.fixture
def mocked_llm_service() -> LLMService:
    # Ensure we test with OpenAI provider
    original_provider = settings.LLM_PROVIDER
    settings.LLM_PROVIDER = LLMProvider.OPENAI
    settings.OPENAI_API_KEY = "fake-key" # Ensure key exists for init

    service = LLMService() 
    service.client = MagicMock() # Mock the OpenAI client
    
    yield service # Use yield to reset settings after test

    # Reset settings
    settings.LLM_PROVIDER = original_provider
    settings.OPENAI_API_KEY = None

# Test initialization
def test_llm_service_init_openai_success():
    settings.LLM_PROVIDER = LLMProvider.OPENAI
    settings.OPENAI_API_KEY = "fake-key" 
    with patch('app.services.llm_service.OpenAI') as MockOpenAI:
        service = LLMService()
        MockOpenAI.assert_called_once_with(api_key="fake-key")
        assert service.client is not None
    settings.OPENAI_API_KEY = None # Clean up

def test_llm_service_init_openai_no_key(caplog):
    settings.LLM_PROVIDER = LLMProvider.OPENAI
    settings.OPENAI_API_KEY = None
    with patch('app.services.llm_service.OpenAI') as MockOpenAI:
        service = LLMService()
        MockOpenAI.assert_not_called()
        assert service.client is None
        assert "OpenAI API key not found" in caplog.text

# Test prompt generation
def test_generate_prompt_mafia(game_state_night):
    service = LLMService() # No client needed for prompt generation
    ai_mafia = next(p for p in game_state_night.players if p.role == Role.MAFIA)
    prompt = service._generate_prompt(ai_mafia, game_state_night)
    
    assert f"You are Player {ai_mafia.id}" in prompt
    assert f"Your Role: {Role.MAFIA.value}" in prompt
    assert "Choose one living player to kill tonight" in prompt
    assert "Available Living Targets" in prompt
    # Check that targets exclude self and dead players
    living_non_mafia = [p for p in game_state_night.players if p.status == PlayerStatus.ALIVE and p.id != ai_mafia.id]
    for target in living_non_mafia:
        assert f"- Player {target.id}" in prompt
    assert "Respond ONLY with a JSON object" in prompt
    assert '{"target_player_id":' in prompt

def test_generate_prompt_villager(game_state_night):
    service = LLMService()
    ai_villager = next(p for p in game_state_night.players if p.role == Role.VILLAGER and not p.is_human)
    prompt = service._generate_prompt(ai_villager, game_state_night)
    assert prompt == "" # Villagers have no night action prompt

# Test action determination (with mocked API calls)
@patch.object(global_llm_service, 'client') # Patch the global instance client used in phase_logic
def test_determine_ai_night_action_mafia_success(mock_openai_client, mocked_llm_service, game_state_night):
    ai_mafia = next(p for p in game_state_night.players if p.role == Role.MAFIA)
    valid_targets = [p for p in game_state_night.players if p.status == PlayerStatus.ALIVE and p.id != ai_mafia.id]
    target_player = valid_targets[0] 

    # Mock the OpenAI API response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"target_player_id": str(target_player.id)})
    mock_openai_client.chat.completions.create.return_value = mock_response
    mocked_llm_service.client = mock_openai_client # Ensure mocked service uses the patched client

    action = mocked_llm_service.determine_ai_night_action(ai_mafia, game_state_night)

    assert isinstance(action, MafiaKillAction)
    assert action.player_id == ai_mafia.id
    assert action.target_id == target_player.id
    mock_openai_client.chat.completions.create.assert_called_once()
    call_args, call_kwargs = mock_openai_client.chat.completions.create.call_args
    assert call_kwargs['model'] == "gpt-3.5-turbo-0125"
    assert 'messages' in call_kwargs
    assert 'response_format' in call_kwargs and call_kwargs['response_format'] == {'type': 'json_object'}

@patch.object(global_llm_service, 'client')
def test_determine_ai_night_action_doctor_success(mock_openai_client, mocked_llm_service, game_state_night):
    ai_doctor = next(p for p in game_state_night.players if p.role == Role.DOCTOR)
    target_player = next(p for p in game_state_night.players if p.role == Role.DETECTIVE) # Doctor protects detective

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"target_player_id": str(target_player.id)})
    mock_openai_client.chat.completions.create.return_value = mock_response
    mocked_llm_service.client = mock_openai_client

    action = mocked_llm_service.determine_ai_night_action(ai_doctor, game_state_night)

    assert isinstance(action, DoctorProtectAction)
    assert action.player_id == ai_doctor.id
    assert action.target_id == target_player.id

@patch.object(global_llm_service, 'client')
def test_determine_ai_night_action_detective_success(mock_openai_client, mocked_llm_service, game_state_night):
    ai_detective = next(p for p in game_state_night.players if p.role == Role.DETECTIVE)
    target_player = next(p for p in game_state_night.players if p.role == Role.MAFIA) # Detective investigates mafia

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"target_player_id": str(target_player.id)})
    mock_openai_client.chat.completions.create.return_value = mock_response
    mocked_llm_service.client = mock_openai_client

    action = mocked_llm_service.determine_ai_night_action(ai_detective, game_state_night)

    assert isinstance(action, DetectiveInvestigateAction)
    assert action.player_id == ai_detective.id
    assert action.target_id == target_player.id

@patch.object(global_llm_service, 'client')
def test_determine_ai_night_action_villager(mock_openai_client, mocked_llm_service, game_state_night):
    ai_villager = next(p for p in game_state_night.players if p.role == Role.VILLAGER and not p.is_human)
    mocked_llm_service.client = mock_openai_client
    
    action = mocked_llm_service.determine_ai_night_action(ai_villager, game_state_night)
    
    assert action is None
    mock_openai_client.chat.completions.create.assert_not_called()

@patch.object(global_llm_service, 'client')
def test_determine_ai_night_action_no_client(mock_openai_client, game_state_night):
    # Simulate no API key / client init failure
    original_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = None
    service_no_client = LLMService() 
    settings.OPENAI_API_KEY = original_key # Restore setting

    ai_mafia = next(p for p in game_state_night.players if p.role == Role.MAFIA)
    action = service_no_client.determine_ai_night_action(ai_mafia, game_state_night)
    assert action is None

@patch.object(global_llm_service, 'client')
def test_determine_ai_night_action_api_error(mock_openai_client, mocked_llm_service, game_state_night):
    ai_mafia = next(p for p in game_state_night.players if p.role == Role.MAFIA)
    
    # Mock API error
    from openai import APIError
    # Adjust APIError instantiation for openai v1.x
    mock_openai_client.chat.completions.create.side_effect = APIError(
        "Service unavailable", 
        request=MagicMock(), # Provide a mock request object
        body=None
    )
    mocked_llm_service.client = mock_openai_client

    with pytest.raises(LLMServiceError, match="OpenAI API error"):
        mocked_llm_service.determine_ai_night_action(ai_mafia, game_state_night)

@patch.object(global_llm_service, 'client')
def test_determine_ai_night_action_json_error(mock_openai_client, mocked_llm_service, game_state_night):
    ai_mafia = next(p for p in game_state_night.players if p.role == Role.MAFIA)
    
    # Mock malformed JSON response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "{'target_player_id':"
    mock_openai_client.chat.completions.create.return_value = mock_response
    mocked_llm_service.client = mock_openai_client

    with pytest.raises(LLMServiceError, match="Failed to parse LLM JSON response"):
        mocked_llm_service.determine_ai_night_action(ai_mafia, game_state_night)
        
@patch.object(global_llm_service, 'client')
def test_determine_ai_night_action_missing_key(mock_openai_client, mocked_llm_service, game_state_night):
    ai_mafia = next(p for p in game_state_night.players if p.role == Role.MAFIA)
    
    # Mock response missing the required key
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"other_key": "some_value"})
    mock_openai_client.chat.completions.create.return_value = mock_response
    mocked_llm_service.client = mock_openai_client

    with pytest.raises(LLMServiceError, match="LLM response missing 'target_player_id'"):
        mocked_llm_service.determine_ai_night_action(ai_mafia, game_state_night)
        
@patch.object(global_llm_service, 'client')
@patch('random.choice') # Mock random.choice for fallback
def test_determine_ai_night_action_invalid_target_fallback(mock_random_choice, mock_openai_client, mocked_llm_service, game_state_night):
    ai_mafia = next(p for p in game_state_night.players if p.role == Role.MAFIA)
    valid_targets = [p for p in game_state_night.players if p.status == PlayerStatus.ALIVE and p.id != ai_mafia.id]
    fallback_target = valid_targets[1] # Choose a specific valid target for fallback
    invalid_target_id = "invalid-player-id" # An ID not in the game state
    
    mock_random_choice.return_value = fallback_target.id

    # Mock the OpenAI API response with an invalid target ID
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"target_player_id": invalid_target_id})
    mock_openai_client.chat.completions.create.return_value = mock_response
    mocked_llm_service.client = mock_openai_client

    action = mocked_llm_service.determine_ai_night_action(ai_mafia, game_state_night)

    # Verify fallback occurred
    assert isinstance(action, MafiaKillAction)
    assert action.target_id == fallback_target.id # Check if it used the fallback target
    mock_random_choice.assert_called_once()
    # Ensure the argument to random.choice was the set of valid target IDs
    valid_target_ids_set = {p.id for p in valid_targets}
    call_args, _ = mock_random_choice.call_args
    assert set(call_args[0]) == valid_target_ids_set 
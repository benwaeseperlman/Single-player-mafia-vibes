import pytest
from unittest.mock import patch, MagicMock
import json
from uuid import uuid4

from app.services.llm_service import LLMService, LLMServiceError, llm_service as global_llm_service
from app.models.game import GameState, GamePhase
from app.models.player import Player, Role, PlayerStatus
from app.models.actions import (
    MafiaKillAction, DoctorProtectAction, DetectiveInvestigateAction,
    ChatMessage # Added import
)
from app.core.config import settings, LLMProvider

# Fixture for a basic game state
@pytest.fixture
def game_state_night() -> GameState:
    p1 = Player(id=str(uuid4()), name="AI Mafia", role=Role.MAFIA, is_human=False)
    p2 = Player(id=str(uuid4()), name="AI Doctor", role=Role.DOCTOR, is_human=False)
    p3 = Player(id=str(uuid4()), name="AI Detective", role=Role.DETECTIVE, is_human=False)
    p4 = Player(id=str(uuid4()), name="AI Villager 1", role=Role.VILLAGER, is_human=False)
    p7 = Player(id=str(uuid4()), name="AI Villager 2", role=Role.VILLAGER, is_human=False)
    p5 = Player(id=str(uuid4()), name="Human Villager", role=Role.VILLAGER, is_human=True)
    p6 = Player(id=str(uuid4()), name="Dead Player", role=Role.VILLAGER, status=PlayerStatus.DEAD, is_human=False)
    
    state = GameState(
        game_id=uuid4(),
        players=[p1, p2, p3, p4, p5, p6, p7],
        phase=GamePhase.NIGHT,
        day_number=1,
        history=["Game started."],
        settings_id=uuid4()
    )
    return state

# Fixture for game state during the Day phase
@pytest.fixture
def game_state_day(game_state_night: GameState) -> GameState:
    game_state_night.phase = GamePhase.DAY
    # Simulate night actions resolved, maybe someone died
    killed_player = next((p for p in game_state_night.players if p.role == Role.VILLAGER and not p.is_human), None)
    if killed_player:
        killed_player.status = PlayerStatus.DEAD
        game_state_night.history.append(f"Night {game_state_night.day_number}: {killed_player.name} was killed. They were a Villager.")
    else: 
        game_state_night.history.append(f"Night {game_state_night.day_number}: The night passed peacefully.")

    # Add some sample chat messages
    p1 = next(p for p in game_state_night.players if p.role == Role.MAFIA)
    p5 = next(p for p in game_state_night.players if p.is_human)
    game_state_night.chat_history = [
        ChatMessage(player_id=p5.id, message="Who do you think it is?"),
        ChatMessage(player_id=p1.id, message="I suspect the Detective, they asked a weird question yesterday.") # Pre-existing message
    ]
    game_state_night.day_number = 1 # Ensure day number is set for day phase
    return game_state_night

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
    prompt = service._generate_night_action_prompt(ai_mafia, game_state_night)
    
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
    prompt = service._generate_night_action_prompt(ai_villager, game_state_night)
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

# -- Tests for Day Discussion --

def test_generate_day_prompt_villager(mocked_llm_service, game_state_day):
    ai_villager = next(p for p in game_state_day.players if p.role == Role.VILLAGER and not p.is_human and p.status == PlayerStatus.ALIVE)
    prompt = mocked_llm_service._generate_day_discussion_prompt(ai_villager, game_state_day, game_state_day.chat_history)

    assert f"You are Player {ai_villager.id}" in prompt
    assert f"Your Role: {Role.VILLAGER.value}" in prompt
    assert "Your goal is to identify and lynch Mafia members" in prompt
    assert "Current Phase: Day 1 Discussion" in prompt
    assert "Living Players:" in prompt
    assert "Recent Events/Announcements:" in prompt
    assert "was killed" in prompt # Check history included
    assert "Recent Chat Messages:" in prompt
    assert "Who do you think it is?" in prompt # Check chat history included
    assert "Respond ONLY with a JSON object" in prompt
    assert '{"chat_message":' in prompt

def test_generate_day_prompt_detective_with_result(mocked_llm_service, game_state_day):
    ai_detective = next(p for p in game_state_day.players if p.role == Role.DETECTIVE and p.status == PlayerStatus.ALIVE)
    ai_detective.investigation_result = "Your investigation revealed Player X is Mafia."
    prompt = mocked_llm_service._generate_day_discussion_prompt(ai_detective, game_state_day, game_state_day.chat_history)

    assert f"Your Role: {Role.DETECTIVE.value}" in prompt
    assert "Use your investigation results subtly" in prompt
    assert "Your Private Information: Your investigation revealed Player X is Mafia." in prompt

def test_generate_day_prompt_mafia_with_allies(mocked_llm_service, game_state_day):
    ai_mafia1 = next(p for p in game_state_day.players if p.role == Role.MAFIA and p.status == PlayerStatus.ALIVE)
    # Add another mafia to test ally prompt
    ai_mafia2 = Player(id=uuid4(), name="AI Mafia 2", role=Role.MAFIA, is_human=False, status=PlayerStatus.ALIVE)
    game_state_day.players.append(ai_mafia2)
    
    prompt = mocked_llm_service._generate_day_discussion_prompt(ai_mafia1, game_state_day, game_state_day.chat_history)

    assert f"Your Role: {Role.MAFIA.value}" in prompt
    assert "Your goal is to eliminate Innocents and avoid suspicion" in prompt
    assert f"Your Mafia Allies (DO NOT REVEAL): {ai_mafia2.id}" in prompt

@patch.object(global_llm_service, 'client')
def test_generate_ai_day_message_success(mock_openai_client, mocked_llm_service, game_state_day):
    ai_villager = next(p for p in game_state_day.players if p.role == Role.VILLAGER and not p.is_human and p.status == PlayerStatus.ALIVE)
    expected_message = "I agree, the Detective has been acting strange."

    # Mock the OpenAI API response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"chat_message": expected_message})
    mock_openai_client.chat.completions.create.return_value = mock_response
    mocked_llm_service.client = mock_openai_client # Ensure mocked service uses the patched client

    chat_message = mocked_llm_service.generate_ai_day_message(ai_villager, game_state_day)

    assert isinstance(chat_message, ChatMessage)
    assert chat_message.player_id == ai_villager.id
    assert chat_message.message == expected_message
    mock_openai_client.chat.completions.create.assert_called_once()
    call_args, call_kwargs = mock_openai_client.chat.completions.create.call_args
    assert call_kwargs['model'] == "gpt-3.5-turbo-0125"
    assert 'messages' in call_kwargs
    assert call_kwargs['temperature'] == 0.8
    assert 'response_format' in call_kwargs and call_kwargs['response_format'] == {'type': 'json_object'}

@patch.object(global_llm_service, 'client')
def test_generate_ai_day_message_api_error(mock_openai_client, mocked_llm_service, game_state_day):
    ai_player = next(p for p in game_state_day.players if not p.is_human and p.status == PlayerStatus.ALIVE)
    from openai import APIError
    mock_openai_client.chat.completions.create.side_effect = APIError("Service unavailable", request=MagicMock(), body=None)
    mocked_llm_service.client = mock_openai_client

    with pytest.raises(LLMServiceError, match="OpenAI API error"):
        mocked_llm_service.generate_ai_day_message(ai_player, game_state_day)

@patch.object(global_llm_service, 'client')
def test_generate_ai_day_message_json_error(mock_openai_client, mocked_llm_service, game_state_day):
    ai_player = next(p for p in game_state_day.players if not p.is_human and p.status == PlayerStatus.ALIVE)
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "not json"
    mock_openai_client.chat.completions.create.return_value = mock_response
    mocked_llm_service.client = mock_openai_client

    with pytest.raises(LLMServiceError, match="Failed to parse LLM JSON response"):
        mocked_llm_service.generate_ai_day_message(ai_player, game_state_day)

@patch.object(global_llm_service, 'client')
def test_generate_ai_day_message_missing_key(mock_openai_client, mocked_llm_service, game_state_day, caplog):
    ai_player = next(p for p in game_state_day.players if not p.is_human and p.status == PlayerStatus.ALIVE)
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"wrong_key": "hello"})
    mock_openai_client.chat.completions.create.return_value = mock_response
    mocked_llm_service.client = mock_openai_client

    message = mocked_llm_service.generate_ai_day_message(ai_player, game_state_day)

    assert message is None
    assert "returned empty or missing 'chat_message'" in caplog.text

@patch.object(global_llm_service, 'client')
def test_generate_ai_day_message_empty_message(mock_openai_client, mocked_llm_service, game_state_day, caplog):
    ai_player = next(p for p in game_state_day.players if not p.is_human and p.status == PlayerStatus.ALIVE)
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"chat_message": "  "})
    mock_openai_client.chat.completions.create.return_value = mock_response
    mocked_llm_service.client = mock_openai_client

    message = mocked_llm_service.generate_ai_day_message(ai_player, game_state_day)

    assert message is None
    assert "returned empty or missing 'chat_message'" in caplog.text 
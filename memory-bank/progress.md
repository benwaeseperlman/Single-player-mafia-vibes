# Project Progress Tracker

## Phase 1: Project Setup & Backend Foundation

### Step 1: Initialize Project Structure (2025-04-27)

- [x] Created root directory (`llm-mafia`)
- [x] Created subdirectories:
  - [x] `backend/` (for FastAPI application)
  - [x] `backend/app/core/` (for core logic and config)
  - [x] `backend/app/models/` (for Pydantic data models)
  - [x] `backend/app/api/` (for API endpoint routers)
  - [x] `backend/app/services/` (for business logic services)
  - [x] `backend/data/` (for storing serialized game states)
  - [x] `frontend/` (for React application)
  - [x] ~~`docs/` (for design/plan documents)~~ - Removed as documents are already in memory-bank
- [x] Created basic `README.md` at the root
- [x] ~~Copied design documents to `docs/` directory~~ - Skipped as documents are already in memory-bank

All directories have been successfully created within `llm-mafia` with the intended structure as per the implementation plan. The README.md provides a basic overview of the project for future developers and users.
*Unit tests written and passed.*

### Step 2: Setup Backend (FastAPI) (2025-04-27)

- [x] Set up a Python virtual environment (`venv`) within `llm-mafia/backend`
- [x] Installed core dependencies: `fastapi`, `uvicorn`, `python-dotenv`, `pydantic`, `websockets`
- [x] Created basic FastAPI app in `llm-mafia/backend/app/main.py` with a health check endpoint
- [x] Created `llm-mafia/backend/app/core/config.py` with settings loaded from environment variables
- [x] Created empty `__init__.py` files in all relevant directories within `llm-mafia/backend/app`
- [x] Created `llm-mafia/backend/.gitignore` file to exclude environment files and data
- [x] Created `llm-mafia/backend/requirements.txt` file with dependencies
- [x] Verified backend is working by running the server and testing health endpoint

The backend server is now set up within `llm-mafia/backend` with a basic FastAPI application structure and a working health check endpoint. Configuration is managed through environment variables and the application is ready for implementing the core game models and logic.
*Unit tests written and passed.*

### Step 3: Define Core Game Models (2025-04-27)

- [x] Created `llm-mafia/backend/app/models/player.py`: Defined `Role`, `PlayerStatus`, `Player` model
- [x] Created `llm-mafia/backend/app/models/game.py`: Defined `GamePhase`, `GameState` model
- [x] Created `llm-mafia/backend/app/models/settings.py`: Defined `GameSettings` model
- [x] Created `llm-mafia/backend/app/models/actions.py`: Defined action and message models
- [x] Created `llm-mafia/backend/app/models/persona.py`: Defined `AIPersona` model
- [x] Created `llm-mafia/backend/app/models/memory.py`: Defined `AIMemory` model
- [x] Updated `llm-mafia/backend/app/models/__init__.py` to export all models

All core game models have been implemented using Pydantic within `llm-mafia/backend/app/models`. The models are structured to support the full game mechanics.
*Unit tests written and passed.*

### Step 4: Implement State Persistence Service (Current Date - replace with actual date)

- [x] Created `llm-mafia/backend/app/services/state_service.py`
- [x] Implemented `save_game_state` function using JSON serialization to save `GameState` to `llm-mafia/backend/data/game_{game_id}.json`.
- [x] Implemented `load_game_state` function to load `GameState` from JSON file.
- [x] Implemented `delete_game_state` function to remove game state files.
- [x] Added basic error handling for file I/O and JSON operations.

State persistence service is implemented within `llm-mafia/backend/app/services` using file-based JSON storage in `llm-mafia/backend/data`. It handles saving, loading, and deleting game state based on `game_id`.
*Unit tests written and passed.*

### Step 5: Implement Game Management Service (Current Date - replace with actual date)

- [x] Created `llm-mafia/backend/app/services/game_manager.py`
- [x] Implemented `GameManager` class to handle game lifecycle.
- [x] Implemented in-memory cache (`active_games`) for active `GameState` objects, using UUIDs as keys.
- [x] Implemented `create_game` method:
    - Generates unique `game_id` (string).
    - Initializes `Player` list based on `GameSettings`.
    - Assigns roles randomly (ensuring one human player).
    - Creates initial `GameState`, storing `settings.id` in `settings_id`.
    - Persists state via `state_service.save_game_state` (passing UUID game_id).
    - Adds game to cache (using UUID game_id).
- [x] Implemented `get_game` method (accepts string ID, uses UUID internally for cache/state_service).
- [x] Implemented `update_game_state` method (accepts string ID, uses UUID internally for cache/state_service).
- [x] Implemented `remove_game_from_cache` method (accepts string ID, uses UUID internally for cache).
- [x] Included basic error handling and logging for invalid UUIDs and operations.
- [x] Added `llm-mafia/backend/setup.py` and installed package in editable mode to aid testing.
- [x] Created unit tests (`llm-mafia/backend/tests/test_game_manager.py`).
- [x] Debugged and fixed import errors (using `sys.path` modification in tests), Pydantic validation errors (`persona_id`), and `UUID` vs `str` inconsistencies.

The `GameManager` service is implemented and unit tested. It provides core logic for creating new games, managing player lists with role assignments, retrieving game states (from cache or storage), and updating/persisting game states, ensuring consistent use of UUIDs internally. Testing setup required adding `setup.py` and modifying `sys.path` in tests.
*Unit tests written and passed.*

### Step 6: Setup Initial API Endpoint (Current Date - replace with actual date)

- [x] Created `llm-mafia/backend/app/api/game_endpoints.py` with FastAPI router.
- [x] Implemented `POST /api/game` endpoint to create a game using `GameManager`.
- [x] Implemented `GET /api/game/{game_id}` endpoint to retrieve game state using `GameManager`.
- [x] Implemented `GET /api/games` endpoint to list saved games using `state_service`.
- [x] Included the `game_endpoints` router in `llm-mafia/backend/app/main.py`.
- [x] Refactored to use a global `GameManager` instance.
- [x] Added `httpx` dependency for testing.
- [x] Created unit tests (`llm-mafia/backend/tests/test_game_endpoints.py`) covering endpoints.

Initial API endpoints for basic game management (create, get, list) are implemented and integrated into the main FastAPI application. Basic error handling (400, 404, 500) is included.
*Unit tests written and passed.*

## Phase 2: Core Game Logic & LLM Integration (Backend)

### Step 7: Implement Phase Logic (2025-04-28 - Replace with actual date)

- [x] Created `llm-mafia/backend/app/services/phase_logic.py`.
- [x] Implemented `advance_to_night`: Updates phase, increments day, clears actions/votes, saves state.
- [x] Implemented `advance_to_day`: Processes night actions (placeholder logic), checks win conditions, updates phase, saves state.
- [x] Implemented `advance_to_voting`: Updates phase, clears votes, saves state.
- [x] Implemented `process_voting_and_advance`: Tallies votes, handles lynching/ties, updates status, checks win conditions, advances phase, saves state.
- [x] Implemented `_check_win_condition` helper.
- [x] Implemented `_resolve_night_actions` helper (placeholder logic).
- [x] Included calls to `save_game_state` at appropriate points.
- [x] Created unit tests (`llm-mafia/backend/tests/test_phase_logic.py`) covering phase transitions, win conditions, placeholder actions/voting, and helper functions.
- [x] Debugged and fixed several issues identified by tests (imports, model usage, assertion logic, mock setup).

Core phase transition logic (Night -> Day -> Voting -> Night) is implemented in `phase_logic.py`. Includes win condition checking and placeholder night action/voting resolution. Comprehensive unit tests ensure logic correctness.
*Unit tests written and passed.*

### Step 8: Implement Role Action Service (2025-04-28 - Replace with actual date)

- [x] Created `llm-mafia/backend/app/services/action_service.py`
- [x] Implemented `ActionService` class.
- [x] Implemented `record_night_action` method with validation (phase, status, role, duplicate, self-kill).
- [x] Utilized existing action models (`MafiaKillAction`, etc.) and `GameState.night_actions`.
- [x] Added `ActionValidationError` custom exception.
- [x] Created unit tests (`llm-mafia/backend/tests/test_action_service.py`) covering success cases and validation errors.

The `ActionService` provides the core functionality for recording night actions (Mafia Kill, Detective Investigate, Doctor Protect). It includes validation logic to ensure actions are permissible according to game rules and player state. Unit tests verify the service's behavior.
*Unit tests written and passed.*

### Step 9: Implement Action Resolution Logic (2025-04-29 - Replace with actual date)

- [x] Updated `_resolve_night_actions` in `llm-mafia/backend/app/services/phase_logic.py` to replace placeholder logic.
- [x] Implemented logic to:
    - Identify Mafia kill target from `game_state.night_actions`.
    - Identify Doctor protection target.
    - Determine if the Doctor's save was successful against the Mafia kill.
    - Update the `status` of the killed player (if any) to `DEAD`.
    - Store the result of the Detective's investigation privately.
    - Generate appropriate public announcements for the Day phase (kill/save/peaceful night).
    - Log internal choices/results (e.g., Doctor protection choice, Detective result) to game history.
    - Clear `game_state.night_actions` after resolution.
- [x] Added `is_saved: bool` and `investigation_result: Optional[str]` fields to `llm-mafia/backend/app/models/player.py` to support action resolution state.
- [x] Created new unit tests specifically for `_resolve_night_actions` in `llm-mafia/backend/tests/test_phase_logic.py`, covering kills, saves, investigations, and edge cases.
- [x] Removed obsolete tests for the previous placeholder logic.
- [x] Debugged and fixed test failures related to:
    - Missing `game_state_night` fixture.
    - `ValueError: "Player" object has no field "is_saved"` (added field to `Player` model).
    - `AttributeError: 'str' object has no attribute 'value'` (corrected enum handling in model config and test fixtures).
    - `NameError: name '_resolve_night_actions' is not defined` (corrected test function call).

Night action resolution logic is now implemented and tested, correctly handling interactions between Mafia, Doctor, and Detective roles based on actions recorded in the game state.
*Unit tests written and passed.*

### Step 10: Implement Basic LLM Integration (for AI Night Actions) (2025-04-29 - Replace with actual date)

- [x] Added `openai` dependency to `llm-mafia/backend/requirements.txt`.
- [x] Updated `llm-mafia/backend/app/core/config.py` to handle provider-specific API keys (`OPENAI_API_KEY`).
- [x] Created `llm-mafia/backend/app/services/llm_service.py` with `LLMService` class.
    - [x] Implemented client initialization (currently OpenAI).
    - [x] Implemented `_generate_prompt` for night actions (Mafia, Doctor, Detective).
    - [x] Implemented `determine_ai_night_action` using OpenAI `chat.completions` API with JSON mode.
    - [x] Added basic validation and fallback logic for LLM target selection.
- [x] Integrated `llm_service.determine_ai_night_action` into `llm-mafia/backend/app/services/phase_logic.py` (`advance_to_night` function).
    - [x] Loops through active, non-human players with night roles.
    - [x] Calls `llm_service` to get action.
    - [x] Calls `action_service.record_night_action` to store the determined action.
    - [x] Added error handling for LLM service and action validation.
- [x] Created `llm-mafia/backend/tests/test_llm_service.py` with unit tests.
    - [x] Mocked OpenAI API calls using `unittest.mock`.
    - [x] Tested client initialization, prompt generation, successful action determination for each role, error handling (API error, JSON error, missing key), and invalid target fallback.
- [x] Debugged and fixed issues related to `requirements.txt` format, Pydantic V2 `BaseSettings` import, action model naming (`DoctorProtectAction`), `GameState` model usage (`day_number`), and test logic (UUID string comparison, `APIError` mocking, assertion checks).

Basic LLM integration for AI night actions is implemented and unit tested. AI players with night roles (Mafia, Doctor, Detective) now use the configured LLM (OpenAI) to decide their target, with results recorded in the game state. Tests cover core functionality and error handling using mocks.
*Unit tests written and passed.*

### Step 11: Implement LLM Integration (for AI Day Discussion) (2025-04-29 - Replace with actual date)

- [x] Added `chat_history: List[ChatMessage]` to `llm-mafia/backend/app/models/game.py`.
- [x] Added `generate_ai_day_message` method to `llm-mafia/backend/app/services/llm_service.py`.
    - [x] Implemented prompt generation (`_generate_day_discussion_prompt`) including game state, recent events, recent chat, role goals, and private info (Mafia allies, Detective results).
    - [x] Uses OpenAI `chat.completions` with JSON mode.
    - [x] Parses response and returns `ChatMessage` object.
    - [x] Includes error handling for API, JSON, and missing/empty messages.
- [x] Integrated `generate_ai_day_message` into `llm-mafia/backend/app/services/phase_logic.py` (`advance_to_day`).
    - [x] Calls LLM service for each living AI player.
    - [x] Appends successful `ChatMessage` results to `game_state.chat_history`.
    - [x] Handles LLM service errors gracefully.
- [x] Added unit tests for `generate_ai_day_message` in `llm-mafia/backend/tests/test_llm_service.py`.
    - [x] Mocked OpenAI API calls.
    - [x] Tested prompt generation for various roles/states.
    - [x] Tested successful message generation and error handling.
    - [x] Fixed test failures related to fixture setup (`StopIteration`).
- [x] Added unit tests for `advance_to_day` integration in `llm-mafia/backend/tests/test_phase_logic.py`.
    - [x] Mocked `llm_service.generate_ai_day_message`.
    - [x] Verified calls to LLM service and addition of messages to `chat_history`.
    - [x] Verified error handling.
    - [x] Fixed test failures related to `ImportError` (missing `action_service` instance) and incorrect `save_game_state` call count assertions.

AI players now generate chat messages during the Day phase using the LLM, considering game context, their role, and recent conversation. Messages are stored in the game state. Unit tests cover the LLM service method and its integration into the phase logic.
*Unit tests written and passed.*

### Step 12: Implement LLM Integration (for AI Voting) (2025-04-29 - Replace with actual date)

- [x] Added `determine_ai_vote` method to `llm-mafia/backend/app/services/llm_service.py`.
    - [x] Implemented prompt generation (`_generate_voting_prompt`) including game state, chat history, role goals, and private info (Mafia allies, Detective results).
    - [x] Added logic to exclude Mafia allies from the list of valid targets in the prompt.
    - [x] Uses OpenAI `chat.completions` with JSON mode.
    - [x] Parses response and returns the chosen player's `UUID`.
    - [x] Includes validation (ensure target is living, handle non-UUID response) and fallback logic (random choice among valid targets).
- [x] Integrated `determine_ai_vote` into `llm-mafia/backend/app/services/phase_logic.py` (`advance_to_voting`).
    - [x] Calls LLM service for each living AI player after clearing previous votes.
    - [x] Directly stores the returned `UUID` (or None) in `game_state.votes`.
    - [x] Handles LLM service errors gracefully.
- [x] Added unit tests for `determine_ai_vote` in `llm-mafia/backend/tests/test_llm_service.py`.
    - [x] Mocked OpenAI API calls.
    - [x] Tested prompt generation (including ally exclusion).
    - [x] Tested successful vote determination for different roles.
    - [x] Tested error handling (API, JSON, missing key) and fallback logic.
    - [x] Debugged and fixed multiple issues related to prompt generation filtering and test assertions.
- [x] Added unit tests for `advance_to_voting` integration in `llm-mafia/backend/tests/test_phase_logic.py`.
    - [x] Mocked `llm_service.determine_ai_vote`.
    - [x] Verified calls to LLM service for living AI players.
    - [x] Verified votes are correctly added to `game_state.votes`.
    - [x] Verified error handling.
    - [x] Debugged and fixed issues related to history message assertions, vote dictionary formats (UUIDs), and mock setups.

AI players now use the LLM to determine their vote during the Voting phase based on game state, chat, and role objectives. Votes are recorded directly in the game state. Unit tests cover the new LLM service method and its integration into the phase logic.
*Unit tests written and passed.*

### Next Steps
- Step 13: Implement WebSocket Manager and Integration - *Not Started*
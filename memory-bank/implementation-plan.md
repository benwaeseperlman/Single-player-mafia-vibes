# LLM Mafia - Implementation Plan

**Version:** 1.0
**Date:** 2025-04-27

## Overview

This document outlines the step-by-step plan for implementing the single-player LLM Mafia game. It assumes the use of the technology stack defined in [`tech-stack.md`](mdc:tech-stack.md) and follows the specifications in the [`game_design_document.md`](mdc:game_design_document.md). The primary goal is to build a functional Minimum Viable Product (MVP) with a focus on modularity and maintainability.

**Target Implementers:** AI Developers / Pair Programming Assistants

## Phase 1: Project Setup & Backend Foundation

1.  **Initialize Project Structure:**
    *   Create root directory (`llm-mafia`).
    *   Create subdirectories:
        *   `backend/` (for FastAPI application)
        *   `frontend/` (for React application)
        *   `docs/` (for design/plan documents - move existing `.md` files here)
        *   `backend/data/` (for storing serialized game states)
    *   Create basic `README.md` at the root.

2.  **Setup Backend (FastAPI):**
    *   Navigate to `backend/`.
    *   Set up a Python virtual environment (e.g., `python -m venv venv`).
    *   Activate the virtual environment.
    *   Install core dependencies: `pip install fastapi uvicorn python-dotenv pydantic websockets`.
    *   Create `backend/app/` directory for application code.
    *   Create `backend/app/main.py` with a basic FastAPI app instance and a health check endpoint (`/health`).
    *   Create `backend/app/core/` for core logic and config.
    *   Create `backend/app/models/` for Pydantic data models.
    *   Create `backend/app/api/` for API endpoint routers.
    *   Create `backend/app/services/` for business logic services.
    *   Create `backend/.env` file for environment variables (e.g., LLM API Key). Add `.env` to `.gitignore`.
    *   Create `backend/requirements.txt`: `pip freeze > requirements.txt`.

3.  **Define Core Game Models (`backend/app/models/`):**
    *   `player.py`: Define `Role` (Enum: MAFIA, DETECTIVE, DOCTOR, VILLAGER), `PlayerStatus` (Enum: ALIVE, DEAD), `Player` (Pydantic model: id, name, role, status, is_human).
    *   `game.py`: Define `GamePhase` (Enum: NIGHT, DAY, PREGAME, GAMEOVER), `GameState` (Pydantic model: game_id, players: List[Player], phase: GamePhase, day_number: int, settings: GameSettings, history: List[str]).
    *   `settings.py`: Define `GameSettings` (Pydantic model: player_count, role_distribution). Player should be able to specify the total number of players and how roles are distributed (e.g., number of mafia, detectives). Optional rules like Doctor restrictions will be added in future updates.
    *   `actions.py`: Define models for night actions (e.g., `MafiaTarget`, `DetectiveInvestigation`, `DoctorProtection`) and voting (`Vote`).
    *   `persona.py`: Define `AIPersona` (e.g., quiet, aggressive, logical, nervous) with traits that influence dialogue style. Structure this for easy addition of more personas later.
    *   `memory.py`: Define `AIMemory` model to store each AI agent's recollection of game events (separate objects for each AI).

4.  **Implement State Persistence Service (`backend/app/services/state_service.py`):**
    *   Create a service for serializing and deserializing game state to/from files.
    *   Implement `save_game_state(game_id, game_state)`: Serializes `GameState` to JSON and saves to a file in `backend/data/{game_id}.json`.
    *   Implement `load_game_state(game_id)`: Loads and deserializes `GameState` from file.
    *   Implement `list_saved_games()`: Returns a list of all saved game IDs.
    *   Include error handling for file operations.

5.  **Implement Basic Game Management (`backend/app/services/game_manager.py`):**
    *   Create a `GameManager` class (or module) to handle game state.
    *   Implement a cache for active `GameState` objects (e.g., a dictionary mapping `game_id` to `GameState`).
    *   Implement `create_game(settings)`: Generates `game_id`, initializes `GameState` with players, assigns roles randomly (ensuring one human player), sets initial phase to `PREGAME` or `NIGHT`. Persists the new game state via `state_service`.
    *   Implement `get_game(game_id)`: First checks the cache, then loads from file via `state_service` if not in memory.
    *   Implement `update_game_state(game_id, new_state)`: Updates the cached state and persists to file via `state_service`.
    *   Implement automatic phase advancement logic - the game should automatically advance to the next phase after all required actions for the current phase are completed.
    *   Add hooks to save game state at critical points (phase changes, actions, votes).

6.  **Setup Initial API Endpoint (`backend/app/api/game_endpoints.py`):**
    *   Create a FastAPI router.
    *   Implement `POST /game` endpoint: Takes game settings (player count, role distribution), calls `game_manager.create_game`, returns the initial `GameState` (or just `game_id` and player role info).
    *   Implement `GET /game/{game_id}` endpoint: Calls `game_manager.get_game`, returns the current `GameState`. Filter sensitive info based on requesting player if needed later.
    *   Implement `GET /games` endpoint: Returns a list of saved games via `state_service.list_saved_games()`.
    *   Include the router in `backend/app/main.py`.

## Phase 2: Core Game Logic & LLM Integration (Backend)

7.  **Implement Phase Logic (`backend/app/services/phase_logic.py`):**
    *   Implement `advance_to_night(game_state)`: Updates phase, handles night start logic.
    *   Implement `advance_to_day(game_state)`: Processes night actions (resolves kills vs. saves), updates player statuses, reveals killed player's role, generates announcements, checks win conditions, updates phase and day number.
    *   Implement `advance_to_voting(game_state)`: Updates phase after discussion.
    *   Implement `process_voting_and_advance(game_state, votes)`: Tallies votes, determines lynched player, updates status, reveals role, generates announcements, checks win conditions, advances to Night or GameOver.
    *   Ensure automatic phase advancement after all required actions for each phase are complete.
    *   Add persistence hooks to save game state after each phase change.

8.  **Implement Role Action Logic (`backend/app/services/action_service.py`):**
    *   Implement functions to handle submissions of night actions (Mafia kill, Detective investigate, Doctor protect). Store these pending actions associated with the `GameState`.
    *   Add validation for action rules.
    *   These actions will be processed by `advance_to_day`.
    *   Track when all required actions are complete to trigger automatic phase advancement.
    *   Persist game state after each action is submitted.

9.  **Implement LLM Interaction Service (`backend/app/services/llm_service.py`):**
    *   Add Google's generative AI Python client library to `requirements.txt` and install.
    *   Create a modular LLM interface:
        *   Create a base `LLMProvider` class or function interface.
        *   Implement the Google AI version as the primary provider.
        *   Design the interface to make it easy to add other providers (OpenAI, Anthropic) later.
    *   Create functions to:
        *   Load API key from `.env`.
        *   Construct prompts for different AI tasks (choosing night action, generating discussion, voting) based on `game_design_document.md` section 3.2. Input should include game state, player role/persona, memory, task description.
        *   Call the LLM API asynchronously.
        *   Parse LLM responses (extract action target, dialogue, vote). Implement robust error handling and retries for malformed responses.
    *   Implement error handling strategy:
        *   Show error messages to the player with options to wait or use a fallback.
        *   Include fallback responses for critical failures.
        *   Provide retry options for temporary issues.

10.  **Integrate LLM for AI Night Actions:**
    *   Modify `advance_to_night` or create a new service function.
    *   For each AI player with a night action:
        *   Call `llm_service` to get their action choice.
        *   Store the AI's chosen action via `action_service`.
    *   Handle potential LLM errors with appropriate fallbacks.

11. **Integrate LLM for AI Day Discussion:**
    *   In `advance_to_day`, after announcements, trigger AI discussion.
    *   For each living AI player:
        *   Call `llm_service` to generate dialogue based on their role, persona, and the current game state/events.
        *   Store/broadcast this dialogue. (Requires WebSocket setup).
    *   Update the AI's memory with new game events and any insights gained.

12. **Integrate LLM for AI Voting:**
    *   When the voting phase begins:
    *   For each living AI player:
        *   Call `llm_service` to get their vote choice.
        *   Collect AI votes.
    *   Handle potential LLM errors with appropriate fallbacks.

13. **Implement WebSocket Communication (`backend/app/api/websocket_manager.py`, `backend/app/main.py`):**
    *   Create a `ConnectionManager` class to handle active WebSocket connections.
    *   Implement a WebSocket endpoint (e.g., `/ws/{game_id}/{player_id}`).
    *   Modify game logic steps (phase changes, actions, discussion, votes, deaths, announcements) to broadcast relevant updates to connected clients via the `ConnectionManager`. Ensure messages are tailored (e.g., Detective results only sent to the Detective).

14. **Add API Endpoints for Player Actions (`backend/app/api/game_endpoints.py`):**
    *   Implement `POST /game/{game_id}/action`: Allows the human player to submit their night action. Calls `action_service`.
    *   Implement `POST /game/{game_id}/message`: Allows the human player to submit a chat message during the Day phase. Broadcast via WebSocket.
    *   Implement `POST /game/{game_id}/vote`: Allows the human player to submit their vote. Collects the vote.
    *   Implement error reporting endpoint to let players know when an LLM call fails and provide options.

## Phase 3: Frontend Development (React)

15. **Setup Frontend (React):**
    *   Navigate to `frontend/`.
    *   Initialize React project (e.g., `npx create-react-app .` or `npm create vite@latest . -- --template react`).
    *   Install necessary dependencies: `npm install axios` (for API calls), potentially a WebSocket client library if needed, state management library (optional).
    *   Clean up default template files.
    *   Set up basic component structure (`frontend/src/components/`, `frontend/src/hooks/`, `frontend/src/services/`).

16. **Implement Core UI Components (`frontend/src/components/`):**
    *   `Game`: Main component orchestrating the UI.
    *   `PlayerList`: Displays players, status, role (if revealed). Highlights human player.
    *   `ChatLog`: Displays game announcements and player messages.
    *   `InputArea`: Text input for human player's chat messages.
    *   `ActionArea`: Context-dependent area for:
        *   Displaying role info.
        *   Night action selection UI (e.g., clickable list of players).
        *   Voting buttons/interface.
    *   `StatusDisplay`: Shows current phase, day number, etc.
    *   `ErrorModal`: For displaying LLM errors with retry/fallback options.
    *   `GameList`: Component to display and select saved games.

17. **Implement API Service (`frontend/src/services/api.js`):**
    *   Create functions to interact with the backend API endpoints (`/game`, `/game/{id}`, `/game/{id}/action`, `/game/{id}/message`, `/game/{id}/vote`, `/games`) using `axios` or `fetch`.
    *   Implement error handling for API requests.

18. **Implement WebSocket Handling (`frontend/src/hooks/useGameWebSocket.js`):**
    *   Create a custom hook or service to manage the WebSocket connection.
    *   Connects to the backend WebSocket endpoint.
    *   Handles incoming messages and updates the client-side game state.
    *   Provides a function to send messages (like chat) via the WebSocket.
    *   Include reconnection logic for dropped connections.

19. **Client-Side State Management (`frontend/src/App.js` or State Library):**
    *   Manage the overall game state received from the backend/WebSocket.
    *   Store human player's role, ID, etc.
    *   Manage UI state (e.g., loading indicators, selected action target).
    *   Use `useState`, `useReducer`, or a library like Zustand/Redux Toolkit.

20. **Connect UI to State and Logic:**
    *   Fetch initial game state on component mount or after joining/starting a game.
    *   Update UI components based on changes in the client-side game state (driven by WebSocket messages).
    *   Wire up input elements (chat, action selection, voting) to call the appropriate API service functions or send WebSocket messages.
    *   Conditionally render UI elements based on game phase and player role (e.g., show action inputs only during Night phase for relevant roles).
    *   Add UI for listing and loading saved games.

## Phase 4: Testing & Refinement

21. **Backend Testing:**
    *   Add unit tests (`pytest`) for core game logic (`phase_logic.py`, `action_service.py`, `game_manager.py`).
    *   Test state serialization and deserialization (`state_service.py`).
    *   Create mock LLM responses for deterministic testing.
    *   Add integration tests for API endpoints and WebSocket communication.
    *   Add actual LLM API tests to validate real response formats (non-deterministic).

22. **Frontend Testing:**
    *   Add basic component tests (e.g., using React Testing Library).
    *   Test API interactions and WebSocket message handling.
    *   Ensure error handling UI works correctly.
    *   Test the game loading/resuming functionality.

23. **End-to-End Testing:**
    *   Manually play through various scenarios and roles.
    *   Test win conditions, role interactions (Doctor save, Detective investigation), AI behavior consistency.
    *   Identify and fix bugs in logic, state synchronization, and UI rendering.
    *   Create test scenarios with both mocked and real LLM responses.
    *   Test server restart scenarios to ensure game state is properly recovered.

24. **Refinement:**
    *   Improve AI prompting based on observed behavior.
    *   Enhance UI/UX based on testing feedback.
    *   Add basic styling (CSS/Tailwind).
    *   Ensure clear error handling and user feedback.
    *   Optimize file I/O operations for game state persistence.

## Game State Persistence

The game will use file-based serialization from the beginning to prevent loss of game state if the server is interrupted:

1. **Implementation Strategy**:
   * Game states will be serialized to JSON files stored in the `backend/data/` directory.
   * Each game will have its own file named with the game ID (e.g., `backend/data/{game_id}.json`).
   * State will be saved at critical points: game creation, phase changes, action submissions, and votes.
   * The server will maintain an in-memory cache for active games but will always persist changes to disk.

2. **Recovery Process**:
   * On server restart, games can be loaded from files as needed.
   * The frontend will be able to list and reconnect to saved games.
   * If a connection is lost during gameplay, the player can rejoin the same game.

3. **Future Enhancement Path**:
   * This file-based approach can later be upgraded to a more robust database (SQLite) if needed, without changing the overall architecture.

## Development Approach

While the plan is presented in phases, the development approach can be flexible. We can work on certain frontend and backend components in parallel when it makes sense (e.g., developing the WebSocket client while implementing the server).

The key principle is to maintain modularity across both backend and frontend, allowing components to be developed and tested independently.

## Future Enhancements (Post-MVP)

*   Implement features listed in `game_design_document.md` section 5.
*   Upgrade to database persistence (SQLite) for better performance with many saved games.
*   Deployment configuration (Dockerfiles, etc.).
*   More sophisticated AI personas and memory.
*   Support for additional LLM providers. 
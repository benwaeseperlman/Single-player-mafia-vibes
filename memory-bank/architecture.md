# LLM Mafia - Architecture Documentation

This document outlines the architecture of the LLM Mafia application, including the purpose of each component and file.

## High-Level Architecture

The application follows a client-server architecture:

- **Frontend**: React-based single-page application
- **Backend**: Python FastAPI server with WebSocket support
- **Data Persistence**: File-based JSON storage (with future path to SQLite)
- **External Services**: LLM API (Google's Generative AI initially)

## Directory Structure

**IMPORTANT:** All source code, tests, configuration files (like Dockerfiles, .env templates), and related assets MUST reside within the `llm-mafia` directory. The root workspace directory should only contain the `llm-mafia` project folder and potentially top-level git files (like `.gitignore`). The `memory-bank` directory is strictly for documentation and progress tracking, not functional code.

### Root Level (within `llm-mafia`)

- `README.md` - Project overview and basic documentation (specific to the `llm-mafia` project)
- `backend/` - Server-side code (Python/FastAPI)
- `frontend/` - Client-side code (React)

### Backend Structure

- `backend/app/` - Main application code
  - `core/` - Core functionality and configuration
    - Contains configuration management (`config.py`)
  - `models/` - Data models (Pydantic)
    - Defines structures for players, game state, settings, actions, personas, memory.
  - `api/` - API endpoint definitions
    - Contains FastAPI routers (e.g., `game_endpoints.py` - *To be implemented*)
  - `services/` - Business logic
    - Implements game mechanics (e.g., `game_manager.py`), state management (`state_service.py`).
- `backend/data/` - Persistent storage location for game state files (JSON).
- `backend/tests/` - Unit and integration tests (`pytest`).
- `backend/setup.py` - Script to make the backend installable for testing.
- `backend/pytest.ini` - Pytest configuration file (used to help with imports).

#### Backend Files Status

1.  `app/main.py` - Implemented (Basic app, health check, CORS)
2.  `app/core/config.py` - Implemented (Loads settings from .env)
3.  `app/models/player.py` - Implemented
4.  `app/models/game.py` - Implemented
5.  `app/models/settings.py` - Implemented
6.  `app/models/actions.py` - Implemented
7.  `app/models/persona.py` - Implemented
8.  `app/models/memory.py` - Implemented
9.  `app/services/state_service.py` - Implemented (File-based JSON persistence)
10. `app/services/game_manager.py` - Implemented (Handles game creation, retrieval, updates, role assignment, caching. Uses `settings_id` and UUIDs consistently.)
11. `app/services/phase_logic.py` - *Pending Implementation*
12. `app/services/action_service.py` - *Pending Implementation*
13. `app/services/llm_service.py` - *Pending Implementation*
14. `app/api/game_endpoints.py` - *Pending Implementation*
15. `app/api/websocket_manager.py` - *Pending Implementation*

### Frontend Structure (Planned)

- `frontend/src/` - Source code
  - `components/` - React components
  - `hooks/` - Custom React hooks
  - `services/` - API and WebSocket interaction
  - `styles/` - CSS/styling files

## Communication Flow

1. Client (React) connects to server via HTTP and WebSocket
2. Players create/join games via REST API
3. Game state updates are pushed to clients via WebSocket
4. Player actions are sent to server via REST API
5. Server processes actions, updates game state, and persists to file
6. LLM service generates AI player behaviors based on game state
7. AI actions and messages are broadcast to connected clients

## Documentation Structure

The project documentation is maintained in the `memory-bank` directory:
- `game_design_document.md` - Game design specifications
- `tech-stack.md` - Technology choices and rationale
- `implementation-plan.md` - Step-by-step implementation plan
- `progress.md` - Implementation progress tracking
- `architecture.md` - This architecture documentation file

This architecture emphasizes:
- Modularity and separation of concerns
- Stateful backend with persistence
- Real-time updates via WebSockets
- Clean API design with FastAPI
- Component-based frontend with React

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
    - Will contain configuration management, environment variables, security utilities
  - `models/` - Data models (Pydantic)
    - Will define the structure for game state, players, actions, etc.
  - `api/` - API endpoint definitions
    - Will contain FastAPI routers for REST endpoints and WebSocket handlers
  - `services/` - Business logic
    - Will implement game mechanics, LLM interaction, state management
- `backend/data/` - Persistent storage location for game state files

#### Planned Backend Files (To be implemented)

1. `app/main.py` - Application entry point and FastAPI app instance
2. `app/core/config.py` - Configuration settings and environment variables
3. `app/models/player.py` - Player models and role definitions  
4. `app/models/game.py` - Game state and phase definitions
5. `app/models/settings.py` - Game settings model
6. `app/models/actions.py` - Models for night actions and voting
7. `app/models/persona.py` - AI persona definitions
8. `app/models/memory.py` - AI memory model
9. `app/services/state_service.py` - Game state serialization and persistence
10. `app/services/game_manager.py` - Game creation and management
11. `app/services/phase_logic.py` - Game phase transitions and logic
12. `app/services/action_service.py` - Role action handling
13. `app/services/llm_service.py` - LLM integration for AI behaviors
14. `app/api/game_endpoints.py` - Game-related API endpoints
15. `app/api/websocket_manager.py` - WebSocket connection management

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

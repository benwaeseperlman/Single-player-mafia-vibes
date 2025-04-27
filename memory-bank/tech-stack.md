# Tech Stack: LLM Mafia Game

This document outlines the technology stack chosen for the single-player, web-based LLM Mafia game. The goal is to use a simple yet robust stack suitable for the project's requirements.

## Frontend

*   **Framework/Library:** React
    *   **Reasoning:** Popular, component-based JavaScript library with a large ecosystem. Suitable for building the required dynamic UI (player lists, chat, action areas).
*   **Styling:** CSS / Tailwind CSS
    *   **Reasoning:** Standard CSS for basic styling, or Tailwind CSS for utility-first, rapid development.

## Backend

*   **Language/Framework:** Python + FastAPI
    *   **Reasoning:** Python offers strong support for AI/LLM integration. FastAPI is a modern, high-performance web framework with built-in asynchronous support (good for LLM API calls), data validation, automatic API documentation, and excellent WebSocket support.

## Real-time Communication

*   **Technology:** WebSockets
    *   **Reasoning:** Enables real-time, bidirectional communication between the server (FastAPI) and the client (React) for pushing game updates, chat messages, and phase changes instantly. FastAPI provides native support.

## LLM Integration

*   **Interface:** Provider's Official Python Client Library (e.g., `openai`, `anthropic`, `google-generativeai`)
    *   **Reasoning:** Simplifies interaction with the chosen Large Language Model's API, handling authentication, request formatting, and response parsing.

## Game State Management

*   **Initial Approach:** In-Memory / File-based
    *   **Reasoning:** For the core single-player loop, managing the active game state within the backend server's memory is the simplest solution. State can be optionally serialized to a file (e.g., JSON) for basic persistence if needed between server restarts for a *running* game.
*   **Future Consideration:** SQLite
    *   **Reasoning:** If features requiring more robust persistence are added (e.g., player statistics, game history), SQLite offers a simple, file-based relational database solution that integrates easily with Python without requiring a separate database server.

## Summary

This stack (React + FastAPI + WebSockets + Python LLM Client) provides a balanced approach, leveraging Python's strengths for the AI backend and FastAPI's modern features, while using React for a dynamic frontend and WebSockets for necessary real-time communication. Initial state management is kept simple, with a clear path for adding database persistence later if required. 
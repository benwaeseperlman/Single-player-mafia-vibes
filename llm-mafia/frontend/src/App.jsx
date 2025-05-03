import React, { useState, useEffect } from 'react';
import GameStatus from './components/GameStatus';
import PlayerList from './components/PlayerList';
import ChatDisplay from './components/ChatDisplay';
import ActionInput from './components/ActionInput';
import MessageInput from './components/MessageInput';

// Placeholder data - replace with actual game state logic
const mockPlayers = [
  { id: 'human-1', name: 'Player 1 (You)', status: 'ALIVE' },
  { id: 'ai-2', name: 'Player 2 (AI)', status: 'ALIVE' },
  { id: 'ai-3', name: 'Player 3 (AI)', status: 'DEAD' },
  { id: 'ai-4', name: 'Player 4 (AI)', status: 'ALIVE' },
];

const mockMessages = [
  { senderName: 'System', text: 'Night falls...' },
  { senderName: 'Player 2 (AI)', text: 'I think Player 4 is suspicious.' },
  { senderName: 'Player 4 (AI)', text: 'No, I saw Player 2 lurking near the bakery!' },
];

function App() {
  // Placeholder state - replace with actual state management (hooks, context, etc.)
  const [gameState, setGameState] = useState({ dayNumber: 1, phase: 'Day' }); // Example phase
  const [players, setPlayers] = useState(mockPlayers);
  const [messages, setMessages] = useState(mockMessages);
  const [humanPlayerId, setHumanPlayerId] = useState('human-1'); // Assuming this ID

  // Placeholder action handlers - replace with API calls
  const handleActionSubmit = (action) => {
    console.log('Action submitted:', action);
    // Example: Send action to backend API
    // Example: Update local state optimistically or wait for WebSocket update
    alert(`Action: ${action.type}, Target: ${action.targetId}`);
  };

  const handleMessageSubmit = (message) => {
    console.log('Message submitted:', message);
    // Example: Send message to backend API
    const newMessage = { senderName: 'Player 1 (You)', text: message };
    setMessages([...messages, newMessage]); // Update local state optimistically
    // Backend should eventually broadcast this via WebSocket
  };

  // TODO: useEffect hook for WebSocket connection and game state updates

  return (
    <div className="App">
      <h1>LLM Mafia Game</h1>
      <GameStatus gameState={gameState} />
      <PlayerList players={players} />
      <ChatDisplay messages={messages} />
      {/* Conditionally render inputs based on phase and human player status */}
      {/* This logic will need refinement based on actual game flow */}
      <MessageInput phase={gameState.phase} onMessageSubmit={handleMessageSubmit} />
      <ActionInput
        phase={gameState.phase}
        players={players.filter(p => p.id !== humanPlayerId)} // Don't allow targeting self in this basic example
        onActionSubmit={handleActionSubmit}
      />
      {/* Add controls to start/create game */}
    </div>
  );
}

export default App;

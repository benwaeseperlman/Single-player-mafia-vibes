import React from 'react';

function GameStatus({ gameState }) {
  // Placeholder: Eventually display phase, day, etc. from gameState
  const { dayNumber = 1, phase = 'Waiting...' } = gameState || {};

  return (
    <div className="game-status">
      <h2>Game Status</h2>
      <p>Day: {dayNumber}</p>
      <p>Phase: {phase}</p>
      {/* Add more game state info here */}
    </div>
  );
}

export default GameStatus; 
import React from 'react';

function PlayerList({ players = [] }) {
  // Placeholder: Eventually display player names, status, etc.

  return (
    <div className="player-list">
      <h2>Players</h2>
      <ul>
        {players.length > 0 ? (
          players.map((player) => (
            <li key={player.id || player.name}> {/* Use a unique key */}
              {player.name} ({player.status || 'Unknown'})
              {/* Add role display logic, buttons for actions/voting */}
            </li>
          ))
        ) : (
          <li>No players yet.</li>
        )}
      </ul>
    </div>
  );
}

export default PlayerList; 
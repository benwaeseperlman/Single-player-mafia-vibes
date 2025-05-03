import React from 'react';

function ActionInput({ phase, players = [], onActionSubmit }) {
  // Placeholder: Show different inputs based on phase (Night action target, Day vote target)

  const handleVote = (targetPlayerId) => {
    console.log(`Voting for: ${targetPlayerId}`);
    if (onActionSubmit) {
      onActionSubmit({ type: 'vote', targetId: targetPlayerId });
    }
  };

  const handleNightAction = (targetPlayerId) => {
      console.log(`Performing night action on: ${targetPlayerId}`);
      if (onActionSubmit) {
          onActionSubmit({ type: 'night_action', targetId: targetPlayerId });
      }
  };

  // Simple example: Show voting buttons during 'Voting' phase
  if (phase === 'Voting') {
    return (
      <div className="action-input">
        <h3>Vote</h3>
        {players.filter(p => p.status === 'ALIVE').map(player => (
          <button key={player.id} onClick={() => handleVote(player.id)}>
            Vote {player.name}
          </button>
        ))}
      </div>
    );
  }

  // Simple example: Show night action buttons during 'Night' phase (assuming a role that targets)
  if (phase === 'Night') {
      return (
          <div className="action-input">
              <h3>Night Action</h3>
              {players.filter(p => p.status === 'ALIVE').map(player => (
                  <button key={player.id} onClick={() => handleNightAction(player.id)}>
                      Target {player.name}
                  </button>
              ))}
          </div>
      );
  }

  return (
    <div className="action-input">
      {/* Action/Voting UI will appear here based on phase and player role */}
      <p>Waiting for correct phase for actions/voting...</p>
    </div>
  );
}

export default ActionInput; 
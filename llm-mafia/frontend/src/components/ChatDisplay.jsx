import React from 'react';

function ChatDisplay({ messages = [] }) {
  // Placeholder: Eventually display formatted chat messages and game events

  return (
    <div className="chat-display">
      <h2>Game Log / Chat</h2>
      <div className="messages-container" style={{ height: '300px', overflowY: 'scroll', border: '1px solid #ccc', marginBottom: '10px', padding: '5px' }}>
        {messages.length > 0 ? (
          messages.map((msg, index) => (
            <p key={index}> {/* Use index as key for now, ideally messages have IDs */}
              <strong>{msg.senderName || 'System'}:</strong> {msg.text}
            </p>
          ))
        ) : (
          <p>No messages yet.</p>
        )}
      </div>
    </div>
  );
}

export default ChatDisplay; 
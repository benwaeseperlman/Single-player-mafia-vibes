import React, { useState } from 'react';

function MessageInput({ phase, onMessageSubmit }) {
  const [message, setMessage] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (message.trim() && onMessageSubmit) {
      console.log(`Submitting message: ${message}`);
      onMessageSubmit(message);
      setMessage(''); // Clear input after submit
    } else {
      console.log('Message submit prevented: Empty message or no submit handler.');
    }
  };

  // Only allow input during the Day phase
  if (phase !== 'Day') {
    return (
        <div className="message-input">
            <p>Discussion happens during the Day phase.</p>
        </div>
    );
  }

  return (
    <div className="message-input">
      <h3>Discuss</h3>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Type your message..."
          style={{ width: '80%', marginRight: '5px' }}
        />
        <button type="submit">Send</button>
      </form>
    </div>
  );
}

export default MessageInput; 
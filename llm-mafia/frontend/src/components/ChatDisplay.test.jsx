import React from 'react';
import { render, screen } from '@testing-library/react';
import ChatDisplay from './ChatDisplay';
import '@testing-library/jest-dom';

describe('ChatDisplay Component', () => {
  test('renders correctly with no messages', () => {
    render(<ChatDisplay />);
    expect(screen.getByText('Game Log / Chat')).toBeInTheDocument();
    expect(screen.getByText('No messages yet.')).toBeInTheDocument();
  });

  test('renders correctly with a list of messages', () => {
    const mockMessages = [
      { senderName: 'System', text: 'Game started' },
      { senderName: 'Alice', text: 'Hello!' },
      { text: 'A lone wolf howls.' }, // Sender defaults to System
    ];
    render(<ChatDisplay messages={mockMessages} />);
    expect(screen.getByText('Game Log / Chat')).toBeInTheDocument();

    // Adjusted assertions to handle split text content
    const message1 = screen.getByText('Game started').closest('p');
    expect(message1).toHaveTextContent('System: Game started');

    const message2 = screen.getByText('Hello!').closest('p');
    expect(message2).toHaveTextContent('Alice: Hello!');

    const message3 = screen.getByText('A lone wolf howls.').closest('p');
    expect(message3).toHaveTextContent('System: A lone wolf howls.');

    expect(screen.queryByText('No messages yet.')).not.toBeInTheDocument();
  });
}); 
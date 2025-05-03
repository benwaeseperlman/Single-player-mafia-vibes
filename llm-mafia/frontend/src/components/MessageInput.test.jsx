import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import MessageInput from './MessageInput';
import '@testing-library/jest-dom';

describe('MessageInput Component', () => {
  test('renders input and button during Day phase', () => {
    render(<MessageInput phase="Day" onMessageSubmit={() => {}} />);
    expect(screen.getByRole('heading', { name: /discuss/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/type your message/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument();
    expect(screen.queryByText(/discussion happens during the day phase/i)).not.toBeInTheDocument();
  });

  test('does not render input/button when not Day phase', () => {
    render(<MessageInput phase="Night" onMessageSubmit={() => {}} />);
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(screen.getByText(/discussion happens during the day phase/i)).toBeInTheDocument();
  });

  test('calls onMessageSubmit with the message when form is submitted', () => {
    const handleSubmit = vi.fn();
    render(<MessageInput phase="Day" onMessageSubmit={handleSubmit} />);

    const input = screen.getByPlaceholderText(/type your message/i);
    const button = screen.getByRole('button', { name: /send/i });

    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.click(button);

    expect(handleSubmit).toHaveBeenCalledTimes(1);
    expect(handleSubmit).toHaveBeenCalledWith('Test message');
    expect(input.value).toBe(''); // Input should clear after submit
  });

  test('does not call onMessageSubmit if message is empty or whitespace', () => {
    const handleSubmit = vi.fn();
    render(<MessageInput phase="Day" onMessageSubmit={handleSubmit} />);

    const input = screen.getByPlaceholderText(/type your message/i);
    const button = screen.getByRole('button', { name: /send/i });

    fireEvent.change(input, { target: { value: '   ' } }); // Whitespace only
    fireEvent.click(button);

    expect(handleSubmit).not.toHaveBeenCalled();
  });

    test('does not call onMessageSubmit if handler is not provided', () => {
        render(<MessageInput phase="Day" />); // No onMessageSubmit prop

        const input = screen.getByPlaceholderText(/type your message/i);
        const button = screen.getByRole('button', { name: /send/i });

        fireEvent.change(input, { target: { value: 'Test' } });
        // Attempt submit (should log an internal message but not throw error)
        expect(() => fireEvent.click(button)).not.toThrow();
    });
}); 
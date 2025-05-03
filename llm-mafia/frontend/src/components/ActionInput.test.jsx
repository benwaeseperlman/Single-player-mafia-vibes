import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import ActionInput from './ActionInput';
import '@testing-library/jest-dom';

const mockPlayers = [
  { id: 'p1', name: 'Alice', status: 'ALIVE' },
  { id: 'p2', name: 'Bob', status: 'ALIVE' },
  { id: 'p3', name: 'Charlie', status: 'DEAD' }, // Dead player should not be targetable
];

describe('ActionInput Component', () => {
  test('renders nothing actionable when phase is not Night or Voting', () => {
    render(<ActionInput phase="Day" players={mockPlayers} />);
    expect(screen.getByText('Waiting for correct phase for actions/voting...')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  test('renders voting buttons during Voting phase', () => {
    const handleSubmit = vi.fn(); // Vitest mock function
    render(<ActionInput phase="Voting" players={mockPlayers} onActionSubmit={handleSubmit} />);

    expect(screen.getByRole('heading', { name: /vote/i })).toBeInTheDocument();
    const voteAliceButton = screen.getByRole('button', { name: /Vote Alice/i });
    const voteBobButton = screen.getByRole('button', { name: /Vote Bob/i });

    expect(voteAliceButton).toBeInTheDocument();
    expect(voteBobButton).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Vote Charlie/i })).not.toBeInTheDocument(); // Dead player

    fireEvent.click(voteBobButton);
    expect(handleSubmit).toHaveBeenCalledTimes(1);
    expect(handleSubmit).toHaveBeenCalledWith({ type: 'vote', targetId: 'p2' });
  });

  test('renders night action buttons during Night phase', () => {
    const handleSubmit = vi.fn();
    render(<ActionInput phase="Night" players={mockPlayers} onActionSubmit={handleSubmit} />);

    expect(screen.getByRole('heading', { name: /night action/i })).toBeInTheDocument();
    const targetAliceButton = screen.getByRole('button', { name: /Target Alice/i });
    const targetBobButton = screen.getByRole('button', { name: /Target Bob/i });

    expect(targetAliceButton).toBeInTheDocument();
    expect(targetBobButton).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Target Charlie/i })).not.toBeInTheDocument(); // Dead player

    fireEvent.click(targetAliceButton);
    expect(handleSubmit).toHaveBeenCalledTimes(1);
    expect(handleSubmit).toHaveBeenCalledWith({ type: 'night_action', targetId: 'p1' });
  });

}); 
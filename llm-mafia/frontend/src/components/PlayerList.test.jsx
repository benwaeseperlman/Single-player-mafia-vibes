import React from 'react';
import { render, screen } from '@testing-library/react';
import PlayerList from './PlayerList';
import '@testing-library/jest-dom';

describe('PlayerList Component', () => {
  test('renders correctly with no players', () => {
    render(<PlayerList />);
    expect(screen.getByText('Players')).toBeInTheDocument();
    expect(screen.getByText('No players yet.')).toBeInTheDocument();
  });

  test('renders correctly with a list of players', () => {
    const mockPlayers = [
      { id: 'p1', name: 'Alice', status: 'ALIVE' },
      { id: 'p2', name: 'Bob', status: 'DEAD' },
      { id: 'p3', name: 'Charlie' }, // Status defaults to Unknown
    ];
    render(<PlayerList players={mockPlayers} />);
    expect(screen.getByText('Players')).toBeInTheDocument();
    expect(screen.getByText(/Alice \(ALIVE\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Bob \(DEAD\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Charlie \(Unknown\)/i)).toBeInTheDocument();
    expect(screen.queryByText('No players yet.')).not.toBeInTheDocument();
  });
}); 
import React from 'react';
import { render, screen } from '@testing-library/react';
import GameStatus from './GameStatus';
import '@testing-library/jest-dom';

describe('GameStatus Component', () => {
  test('renders correctly with default props', () => {
    render(<GameStatus />);
    expect(screen.getByText('Game Status')).toBeInTheDocument();
    expect(screen.getByText(/Day: 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Phase: Waiting.../i)).toBeInTheDocument();
  });

  test('renders correctly with provided gameState', () => {
    const mockGameState = { dayNumber: 5, phase: 'Night' };
    render(<GameStatus gameState={mockGameState} />);
    expect(screen.getByText('Game Status')).toBeInTheDocument();
    expect(screen.getByText(/Day: 5/i)).toBeInTheDocument();
    expect(screen.getByText(/Phase: Night/i)).toBeInTheDocument();
  });
}); 
import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from './App';

describe('App component', () => {
  it('renders the main heading', () => {
    render(<App />);
    // Check if the heading "LLM Mafia" is in the document
    const headingElement = screen.getByRole('heading', { name: /llm mafia/i });
    expect(headingElement).toBeInTheDocument();
  });

  // Add more tests here later as functionality grows
}); 
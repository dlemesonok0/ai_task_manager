import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import App from './App';

// Mock fetch
global.fetch = vi.fn();

describe('App', () => {
  it('renders dashboard title', () => {
    render(<App />);
    const titleElement = screen.getByText(/AI Task Manager/i);
    expect(titleElement).toBeInTheDocument();
  });

  it('shows loading state initially', () => {
    render(<App />);
    expect(screen.getByText(/Syncing with Todoist/i)).toBeInTheDocument();
  });
});

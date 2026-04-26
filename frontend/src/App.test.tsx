import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from './App';

// Mock data
const mockTasks = [
  { id: '1', content: 'Task 1', priority: 1, due: 'today' },
  { id: '2', content: 'Task 2', priority: 4, due: 'tomorrow' }
];

const mockEvents = [
  { 
    id: 'e1', 
    summary: 'Meeting', 
    start: { dateTime: '2026-04-26T10:00:00Z' }, 
    end: { dateTime: '2026-04-26T11:00:00Z' } 
  }
];

describe('App Component', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('renders loading state initially', () => {
    (fetch as any).mockResolvedValue({
      ok: true,
      json: async () => []
    });
    
    render(<App />);
    expect(screen.getByText(/Syncing with Todoist/i)).toBeInTheDocument();
  });

  it('renders tasks and events after fetching', async () => {
    (fetch as any).mockImplementation((url: string) => {
      if (url.includes('/api/tasks')) {
        return Promise.resolve({ ok: true, json: async () => mockTasks });
      }
      if (url.includes('/api/events')) {
        return Promise.resolve({ ok: true, json: async () => mockEvents });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.queryByText(/Syncing with Todoist/i)).not.toBeInTheDocument();
    });

    expect(screen.getByText('Task 1')).toBeInTheDocument();
    expect(screen.getByText('Task 2')).toBeInTheDocument();
    expect(screen.getByText('Meeting')).toBeInTheDocument();
  });

  it('can add a new task', async () => {
    (fetch as any).mockImplementation((url: string, options?: any) => {
      if (options?.method === 'POST') {
        return Promise.resolve({ ok: true });
      }
      return Promise.resolve({ ok: true, json: async () => [] });
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.queryByText(/Syncing with Todoist/i)).not.toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/What needs to be done today?/i);
    const button = screen.getByRole('button', { name: /Add Task/i });

    fireEvent.change(input, { target: { value: 'Buy Milk' } });
    fireEvent.click(button);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/api/tasks'), expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('Buy Milk')
      }));
    });

    // Check that input is cleared
    expect((input as HTMLInputElement).value).toBe('');
  });

  it('handles fetch errors gracefully', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    (fetch as any).mockRejectedValue(new Error('Network Error'));

    render(<App />);

    await waitFor(() => {
      expect(screen.queryByText(/Syncing with Todoist/i)).not.toBeInTheDocument();
    });

    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  it('handles error when adding a task', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    (fetch as any).mockImplementation((url: string, options?: any) => {
      if (options?.method === 'POST') {
        return Promise.reject(new Error('Submit Failed'));
      }
      return Promise.resolve({ ok: true, json: async () => [] });
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.queryByText(/Syncing with Todoist/i)).not.toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/What needs to be done today?/i);
    const button = screen.getByRole('button', { name: /Add Task/i });

    fireEvent.change(input, { target: { value: 'Bad Task' } });
    fireEvent.click(button);

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalled();
    });

    consoleSpy.mockRestore();
  });
});

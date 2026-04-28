import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from './App';

// Mock data
const mockTasks = [
  { id: '1', content: 'Task 1', priority: 1, due: 'today' },
  { id: '2', content: 'Task 2', priority: 4, due: 'tomorrow' },
  { id: '3', content: 'Task 3', priority: 2, due: null }
];

const mockEvents = [
  { 
    id: 'e1', 
    summary: 'Meeting', 
    start: { dateTime: new Date().toISOString() }, 
    end: { dateTime: new Date(Date.now() + 60 * 60 * 1000).toISOString() },
    calendarId: 'primary'
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
    expect(screen.getByText('Task 3')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Today' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Tomorrow' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'No due date' })).toBeInTheDocument();
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

    await waitFor(() => {
      expect((input as HTMLInputElement).value).toBe('');
    });
  });

  it('can edit a calendar event', async () => {
    (fetch as any).mockImplementation((url: string, options?: any) => {
      if (options?.method === 'PATCH') {
        return Promise.resolve({ ok: true, json: async () => ({ ...mockEvents[0], summary: 'Updated Meeting' }) });
      }
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

    fireEvent.click(screen.getByRole('button', { name: /Meeting/i }));
    const titleInput = screen.getByLabelText(/Title/i);

    fireEvent.change(titleInput, { target: { value: 'Updated Meeting' } });
    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/api/events/e1'), expect.objectContaining({
        method: 'PATCH',
        body: expect.stringContaining('Updated Meeting')
      }));
    });
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

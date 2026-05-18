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
    localStorage.clear();
    localStorage.setItem('ai-task-manager-token', 'test-token');
    vi.stubGlobal('fetch', vi.fn());
  });

  it('renders sign in form when no session token exists', () => {
    localStorage.clear();
    render(<App />);
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('can sign in and store the access token', async () => {
    localStorage.clear();
    (fetch as any).mockImplementation((url: string) => {
      if (url.includes('/api/auth/login')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ access_token: 'new-token', token_type: 'bearer' })
        });
      }
      return Promise.resolve({ ok: true, json: async () => [] });
    });

    render(<App />);

    fireEvent.change(screen.getByLabelText(/Username/i), { target: { value: 'admin' } });
    fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'secret' } });
    fireEvent.click(screen.getAllByRole('button', { name: /^Sign in$/i }).at(-1)!);

    await waitFor(() => {
      expect(localStorage.getItem('ai-task-manager-token')).toBe('new-token');
    });
  });

  it('can switch to register mode', () => {
    localStorage.clear();
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: /^Register$/i }));
    expect(screen.getByRole('heading', { name: 'Create account' })).toBeInTheDocument();
  });

  it('can save integration tokens', async () => {
    (fetch as any).mockImplementation((url: string, options?: any) => {
      if (url.includes('/api/integrations') && options?.method === 'PUT') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            todoist_connected: true,
            google_connected: true,
            telegram_connected: true,
            telegram_username: 'test_user',
            telegram_linked_at: new Date().toISOString()
          })
        });
      }
      if (url.includes('/api/telegram/link-code')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            code: 'ABCD1234',
            command: '/link ABCD1234',
            expires_at: new Date(Date.now() + 15 * 60 * 1000).toISOString()
          })
        });
      }
      if (url.includes('/api/integrations')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            todoist_connected: false,
            google_connected: false,
            telegram_connected: false,
            telegram_username: null,
            telegram_linked_at: null
          })
        });
      }
      if (url.includes('/api/sync')) {
        return Promise.resolve({ ok: true, json: async () => ({}) });
      }
      return Promise.resolve({ ok: true, json: async () => [] });
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.queryByText(/Syncing with Todoist/i)).not.toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/Todoist API token/i), { target: { value: 'todoist-token' } });
    fireEvent.change(screen.getByPlaceholderText(/Google Calendar token/i), { target: { value: '{"token":"google"}' } });
    fireEvent.click(screen.getByRole('button', { name: /Create Telegram link/i }));

    await waitFor(() => {
      expect(screen.getByDisplayValue('/link ABCD1234')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Save integrations/i }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/api/integrations'), expect.objectContaining({
        method: 'PUT',
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
        body: expect.stringContaining('todoist-token')
      }));
    });
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
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
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
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
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

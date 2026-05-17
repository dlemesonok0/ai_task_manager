import { useState, useEffect } from 'react';
import './index.css';

interface Task {
  id: string;
  content: string;
  priority: number;
  due: string | null;
}

interface Event {
  id: string;
  summary: string;
  start: { dateTime?: string; date?: string };
  end: { dateTime?: string; date?: string };
  calendarId?: string;
}

interface EventEditorState {
  id: string;
  calendarId: string;
  summary: string;
  start: string;
  end: string;
}

interface TaskGroup {
  title: string;
  tasks: Task[];
}

interface CalendarDay {
  date: Date;
  events: Event[];
}

const taskGroupOrder = ['today', 'tomorrow', 'upcoming', 'no-date'] as const;

const getTaskGroupKey = (due: string | null) => {
  if (!due) return 'no-date';

  const normalizedDue = due.toLowerCase();
  if (normalizedDue.includes('today')) return 'today';
  if (normalizedDue.includes('tomorrow')) return 'tomorrow';

  return 'upcoming';
};

const taskGroupLabels: Record<(typeof taskGroupOrder)[number], string> = {
  today: 'Today',
  tomorrow: 'Tomorrow',
  upcoming: 'Upcoming',
  'no-date': 'No due date'
};

const dateKey = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const getEventStartDate = (event: Event) => {
  const startValue = event.start?.dateTime || event.start?.date;
  return startValue ? new Date(startValue) : null;
};

const getEventEndDate = (event: Event) => {
  const endValue = event.end?.dateTime || event.end?.date;
  return endValue ? new Date(endValue) : null;
};

const toDatetimeLocalValue = (date: Date) => {
  const offsetMs = date.getTimezoneOffset() * 60 * 1000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
};

const fromDatetimeLocalValue = (value: string) => new Date(value).toISOString();

const dayStartHour = 7;
const dayEndHour = 22;
const timelineHourHeight = 64;
const authTokenStorageKey = 'ai-task-manager-token';

function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState('');
  const [editingEvent, setEditingEvent] = useState<EventEditorState | null>(null);
  const [savingEvent, setSavingEvent] = useState(false);
  const [authToken, setAuthToken] = useState(() => localStorage.getItem(authTokenStorageKey) || '');
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [authenticating, setAuthenticating] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [integrations, setIntegrations] = useState({
    todoist_api_token: '',
    google_token_json: ''
  });
  const [integrationStatus, setIntegrationStatus] = useState({
    todoist_connected: false,
    google_connected: false,
    telegram_connected: false,
    telegram_username: null as string | null,
    telegram_linked_at: null as string | null
  });
  const [savingIntegrations, setSavingIntegrations] = useState(false);
  const [telegramLinkCommand, setTelegramLinkCommand] = useState('');
  const [telegramLinkExpiresAt, setTelegramLinkExpiresAt] = useState('');
  const [creatingTelegramLink, setCreatingTelegramLink] = useState(false);

  const API_BASE_URL = import.meta.env.VITE_API_URL || '';

  const [newTask, setNewTask] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const authHeaders = authToken ? { Authorization: `Bearer ${authToken}` } : {};

  const clearSession = () => {
    localStorage.removeItem(authTokenStorageKey);
    setAuthToken('');
    setTasks([]);
    setEvents([]);
    setEditingEvent(null);
    setFetchError('');
    setLoading(false);
  };

  const fetchData = async () => {
    if (!authToken) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setFetchError('');
    try {
      const [tasksRes, eventsRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/tasks`, { headers: authHeaders }),
        fetch(`${API_BASE_URL}/api/events`, { headers: authHeaders })
      ]);

      if (tasksRes.status === 401 || eventsRes.status === 401) {
        clearSession();
        return;
      }
      
      if (!tasksRes.ok || !eventsRes.ok) {
        setFetchError('Could not load today\'s plan. Refresh to try again.');
        return;
      }

      setTasks(await tasksRes.json());
      setEvents(await eventsRes.json());
    } catch (err) {
      console.error("Failed to fetch data:", err);
      setFetchError('Could not load today\'s plan. Refresh to try again.');
    } finally {
      setLoading(false);
    }
  };

  const fetchIntegrations = async () => {
    if (!authToken) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/integrations`, { headers: authHeaders });
      if (res.status === 401) {
        clearSession();
        return;
      }
      if (res.ok) {
        setIntegrationStatus(await res.json());
      }
    } catch (err) {
      console.error("Failed to fetch integrations:", err);
    }
  };

  useEffect(() => {
    fetchData();
    fetchIntegrations();
  }, [authToken]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError('');
    setAuthenticating(true);

    try {
      const endpoint = authMode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const res = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });

      if (!res.ok) {
        setAuthError(authMode === 'login' ? 'Invalid username or password' : 'Could not create account');
        return;
      }

      const data = await res.json();
      localStorage.setItem(authTokenStorageKey, data.access_token);
      setAuthToken(data.access_token);
      setPassword('');
    } catch (err) {
      console.error("Login failed:", err);
      setAuthError('Authentication service is unavailable');
    } finally {
      setAuthenticating(false);
    }
  };

  const handleAddTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTask.trim()) return;
    
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ content: newTask, priority: 1, due_string: 'today' })
      });

      if (res.status === 401) {
        clearSession();
        return;
      }
      
      if (res.ok) {
        setNewTask('');
        await fetchData(); // Refresh list
      }
    } catch (err) {
      console.error("Error adding task:", err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleSaveIntegrations = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingIntegrations(true);
    try {
      const payload = Object.fromEntries(
        Object.entries(integrations).map(([key, value]) => [key, value.trim() || null])
      );
      const res = await fetch(`${API_BASE_URL}/api/integrations`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify(payload)
      });

      if (res.status === 401) {
        clearSession();
        return;
      }

      if (res.ok) {
        setIntegrationStatus(await res.json());
        setIntegrations({ todoist_api_token: '', google_token_json: '' });
        await handleSync();
      }
    } catch (err) {
      console.error("Error saving integrations:", err);
    } finally {
      setSavingIntegrations(false);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/sync`, {
        method: 'POST',
        headers: authHeaders
      });

      if (res.status === 401) {
        clearSession();
        return;
      }

      if (res.ok) {
        await fetchData();
      }
    } catch (err) {
      console.error("Error syncing data:", err);
    } finally {
      setSyncing(false);
    }
  };

  const handleCreateTelegramLink = async () => {
    setCreatingTelegramLink(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/telegram/link-code`, {
        method: 'POST',
        headers: authHeaders
      });

      if (res.status === 401) {
        clearSession();
        return;
      }

      if (res.ok) {
        const data = await res.json();
        setTelegramLinkCommand(data.command);
        setTelegramLinkExpiresAt(data.expires_at);
      }
    } catch (err) {
      console.error("Error creating Telegram link code:", err);
    } finally {
      setCreatingTelegramLink(false);
    }
  };

  const openEventEditor = (event: Event) => {
    const start = getEventStartDate(event);
    const end = getEventEndDate(event);
    if (!start || !end) return;

    setEditingEvent({
      id: event.id,
      calendarId: event.calendarId || 'primary',
      summary: event.summary || '',
      start: toDatetimeLocalValue(start),
      end: toDatetimeLocalValue(end)
    });
  };

  const handleUpdateEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingEvent) return;

    setSavingEvent(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/events/${encodeURIComponent(editingEvent.id)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({
          calendar_id: editingEvent.calendarId,
          summary: editingEvent.summary,
          start: fromDatetimeLocalValue(editingEvent.start),
          end: fromDatetimeLocalValue(editingEvent.end)
        })
      });

      if (res.status === 401) {
        clearSession();
        return;
      }

      if (res.ok) {
        setEditingEvent(null);
        await fetchData();
      }
    } catch (err) {
      console.error("Error updating event:", err);
    } finally {
      setSavingEvent(false);
    }
  };

  const formatTime = (isoString?: string) => {
    if (!isoString) return 'All Day';
    return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const formatDayName = (date: Date) => date.toLocaleDateString([], { weekday: 'short' });

  const formatDayNumber = (date: Date) => date.toLocaleDateString([], { day: 'numeric', month: 'short' });

  const formatFullDay = (date: Date) =>
    date.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });

  const getEventBlockStyle = (event: Event) => {
    const start = getEventStartDate(event);
    const end = getEventEndDate(event);
    if (!start || !end) return {};

    const startMinutes = Math.max(0, (start.getHours() - dayStartHour) * 60 + start.getMinutes());
    const durationMinutes = Math.max(30, (end.getTime() - start.getTime()) / 60000);
    const top = (startMinutes / 60) * timelineHourHeight;
    const height = Math.max(34, (durationMinutes / 60) * timelineHourHeight);

    return { top: `${top}px`, height: `${height}px` };
  };

  const backlogTasks = tasks.filter((task) => getTaskGroupKey(task.due) !== 'today');
  const groupedTasks: TaskGroup[] = taskGroupOrder
    .map((groupKey) => ({
      title: taskGroupLabels[groupKey],
      tasks: backlogTasks.filter((task) => getTaskGroupKey(task.due) === groupKey)
    }))
    .filter((group) => group.tasks.length > 0);

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const todayTasks = tasks.filter((task) => getTaskGroupKey(task.due) === 'today');
  const overdueTasks = tasks.filter((task) => {
    if (!task.due) return false;
    const dueDate = new Date(task.due);
    return !Number.isNaN(dueDate.getTime()) && dueDate < today;
  });
  const nextEvents = events
    .filter((event) => {
      const start = getEventStartDate(event);
      return start ? start >= today : false;
    })
    .sort((first, second) => {
      const firstStart = getEventStartDate(first)?.getTime() || 0;
      const secondStart = getEventStartDate(second)?.getTime() || 0;
      return firstStart - secondStart;
    })
    .slice(0, 5);
  const todayEvents = events.filter((event) => {
    const start = getEventStartDate(event);
    return start ? dateKey(start) === dateKey(today) : false;
  });
  const integrationConnectionStates = [
    integrationStatus.todoist_connected,
    integrationStatus.google_connected,
    integrationStatus.telegram_connected
  ];
  const connectedIntegrations = integrationConnectionStates.filter(Boolean).length;
  const totalIntegrations = integrationConnectionStates.length;
  const hasPlanItems = todayTasks.length > 0 || todayEvents.length > 0 || overdueTasks.length > 0;

  const calendarDays: CalendarDay[] = Array.from({ length: 7 }, (_, index) => {
    const date = new Date();
    date.setHours(0, 0, 0, 0);
    date.setDate(date.getDate() + index);

    return {
      date,
      events: events.filter((event) => {
        const eventDate = getEventStartDate(event);
        return eventDate ? dateKey(eventDate) === dateKey(date) : false;
      })
    };
  });

  const timelineHours = Array.from(
    { length: dayEndHour - dayStartHour + 1 },
    (_, index) => dayStartHour + index
  );

  return (
    <div>
      <div className="app-header">
        <h1>AI Task Manager</h1>
        {authToken && (
          <div className="header-actions">
            <button type="button" className="btn-secondary" onClick={handleSync} disabled={syncing}>
              {syncing ? 'Syncing...' : 'Refresh'}
            </button>
            <button type="button" className="btn-secondary" onClick={clearSession}>
              Sign out
            </button>
          </div>
        )}
      </div>

      {!authToken ? (
        <form onSubmit={handleLogin} className="auth-panel">
          <div className="auth-tabs">
            <button type="button" className={authMode === 'login' ? 'active' : ''} onClick={() => setAuthMode('login')}>
              Sign in
            </button>
            <button type="button" className={authMode === 'register' ? 'active' : ''} onClick={() => setAuthMode('register')}>
              Register
            </button>
          </div>
          <h2>{authMode === 'login' ? 'Sign in' : 'Create account'}</h2>
          <label>
            Username
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          {authError && <p className="auth-error">{authError}</p>}
          <button type="submit" className="btn-primary" disabled={authenticating}>
            {authenticating ? 'Please wait...' : authMode === 'login' ? 'Sign in' : 'Register'}
          </button>
        </form>
      ) : (
        <>
          <section className="today-hero">
            <div>
              <span className="eyebrow">{formatFullDay(today)}</span>
              <h2>Today</h2>
              <p>
                {loading
                  ? 'Syncing with Todoist & Google Calendar...'
                  : fetchError
                    ? 'Your day plan needs a refresh.'
                    : hasPlanItems
                      ? `${todayTasks.length} tasks, ${todayEvents.length} events, ${overdueTasks.length} overdue`
                      : 'Nothing is scheduled for today yet.'}
              </p>
            </div>
            <div className="hero-metrics" aria-label="Today overview">
              <div>
                <strong>{todayTasks.length}</strong>
                <span>Today tasks</span>
              </div>
              <div>
                <strong>{todayEvents.length}</strong>
                <span>Events</span>
              </div>
              <div className={overdueTasks.length > 0 ? 'attention' : ''}>
                <strong>{overdueTasks.length}</strong>
                <span>Overdue</span>
              </div>
            </div>
          </section>

          {fetchError && (
            <div className="state-banner error-state">
              <strong>Data did not load.</strong>
              <span>{fetchError}</span>
            </div>
          )}

          <form onSubmit={handleAddTask} className="quick-add-panel">
            <input
              type="text"
              value={newTask}
              onChange={(e) => setNewTask(e.target.value)}
              placeholder="What needs to be done today?"
            />
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? 'Adding...' : 'Add Task'}
            </button>
          </form>

          {loading ? (
            <div className="loading-grid">
              <div className="skeleton-panel" />
              <div className="skeleton-panel" />
              <div className="skeleton-panel wide" />
            </div>
          ) : (
            <>
              <div className="dashboard-grid">
                <section className="panel-primary">
                  <div className="section-header">
                    <div>
                      <span className="eyebrow">Focus</span>
                      <h2>Today tasks</h2>
                    </div>
                    <span className="count-pill">{todayTasks.length}</span>
                  </div>
                  <div className="item-list">
                    {todayTasks.length === 0 ? (
                      <div className="empty-state">
                        <strong>No tasks due today.</strong>
                        <span>Add a task above or sync Todoist to build your plan.</span>
                      </div>
                    ) : (
                      todayTasks.map((task) => (
                        <div key={task.id} className={`item-card priority-${task.priority}`}>
                          <div className="item-title">{task.content}</div>
                          <div className="item-meta">
                            <span>Priority: P{5 - task.priority}</span>
                            {task.due && <span>Due: {task.due}</span>}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </section>

                <section className="panel-primary">
                  <div className="section-header">
                    <div>
                      <span className="eyebrow">Schedule</span>
                      <h2>Upcoming events</h2>
                    </div>
                    <span className="count-pill">{nextEvents.length}</span>
                  </div>
                  <div className="item-list">
                    {nextEvents.length === 0 ? (
                      <div className="empty-state">
                        <strong>No upcoming events.</strong>
                        <span>Connect Google Calendar or add calendar items to see your day here.</span>
                      </div>
                    ) : (
                      nextEvents.map((event) => (
                        <div
                          key={event.id}
                          className="event-row"
                          aria-label={`${event.summary || 'Untitled event'} at ${formatTime(event.start?.dateTime || event.start?.date)}`}
                        >
                          <span>{formatTime(event.start?.dateTime || event.start?.date)}</span>
                          <strong>Calendar event</strong>
                        </div>
                      ))
                    )}
                  </div>
                </section>
              </div>

              <div className="dashboard-grid secondary-grid">
                <section className="panel-secondary">
                  <div className="section-header">
                    <div>
                      <span className="eyebrow">Carryover</span>
                      <h2>Overdue tasks</h2>
                    </div>
                    <span className={overdueTasks.length > 0 ? 'count-pill danger' : 'count-pill'}>
                      {overdueTasks.length}
                    </span>
                  </div>
                  {overdueTasks.length === 0 ? (
                    <div className="empty-state compact">
                      <strong>No overdue work.</strong>
                      <span>Nothing is blocking today from previous dates.</span>
                    </div>
                  ) : (
                    <div className="item-list">
                      {overdueTasks.map((task) => (
                        <div key={task.id} className={`item-card priority-${task.priority}`}>
                          <div className="item-title">{task.content}</div>
                          <div className="item-meta">
                            <span>Priority: P{5 - task.priority}</span>
                            {task.due && <span>Due: {task.due}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </section>

                <form onSubmit={handleSaveIntegrations} className="panel-secondary integrations-panel">
                  <div className="section-header">
                    <div>
                      <span className="eyebrow">Connections</span>
                      <h2>Integrations</h2>
                    </div>
                    <span className="count-pill">{connectedIntegrations}/{totalIntegrations}</span>
                  </div>
                  {connectedIntegrations === 0 && (
                    <div className="empty-state compact">
                      <strong>No integrations connected.</strong>
                      <span>Add tokens below to sync tasks, events, and notifications.</span>
                    </div>
                  )}
                  <div className="integration-status">
                    <span className={integrationStatus.todoist_connected ? 'connected' : ''}>Todoist</span>
                    <span className={integrationStatus.google_connected ? 'connected' : ''}>Google Calendar</span>
                    <span className={integrationStatus.telegram_connected ? 'connected' : ''}>Telegram Bot</span>
                  </div>
                  <input
                    type="password"
                    value={integrations.todoist_api_token}
                    onChange={(e) => setIntegrations({ ...integrations, todoist_api_token: e.target.value })}
                    placeholder="Todoist API token"
                  />
                  <textarea
                    value={integrations.google_token_json}
                    onChange={(e) => setIntegrations({ ...integrations, google_token_json: e.target.value })}
                    placeholder="Google Calendar token.json content"
                    rows={3}
                  />
                  <input
                    type="password"
                    value={telegramLinkCommand}
                    readOnly
                    placeholder="Generate a Telegram link command"
                  />
                  {telegramLinkExpiresAt && (
                    <span className="integration-help">
                      Send this command to the system bot before {new Date(telegramLinkExpiresAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}.
                    </span>
                  )}
                  {integrationStatus.telegram_username && (
                    <span className="integration-help">Linked to {integrationStatus.telegram_username}</span>
                  )}
                  <button type="button" className="btn-secondary" onClick={handleCreateTelegramLink} disabled={creatingTelegramLink}>
                    {creatingTelegramLink ? 'Creating link...' : 'Create Telegram link'}
                  </button>
                  <button type="submit" className="btn-primary" disabled={savingIntegrations}>
                    {savingIntegrations ? 'Saving...' : 'Save integrations'}
                  </button>
                </form>
              </div>

              <section className="panel-secondary">
                <div className="section-header">
                  <div>
                    <span className="eyebrow">Backlog</span>
                    <h2>Active Tasks</h2>
                  </div>
                  <span className="count-pill">{backlogTasks.length}</span>
                </div>
                <div className="item-list">
                  {backlogTasks.length === 0 ? (
                    <div className="empty-state">
                      <strong>No later tasks found.</strong>
                      <span>Tomorrow, upcoming, and unscheduled tasks will appear here.</span>
                    </div>
                  ) : (
                    groupedTasks.map((group) => (
                      <div key={group.title} className="task-group">
                        <div className="task-group-header">
                          <h3>{group.title}</h3>
                          <span>{group.tasks.length}</span>
                        </div>
                        <div className="task-group-list">
                          {group.tasks.map((task) => (
                            <div key={task.id} className={`item-card priority-${task.priority}`}>
                              <div className="item-title">{task.content}</div>
                              <div className="item-meta">
                                <span>Priority: P{5 - task.priority}</span>
                                {task.due && <span>Due: {task.due}</span>}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </section>

              <section className="panel-secondary">
                <div className="section-header">
                  <div>
                    <span className="eyebrow">Calendar</span>
                    <h2>Week timeline</h2>
                  </div>
                  <span className="count-pill">{events.length}</span>
                </div>
                {events.length === 0 ? (
                  <div className="empty-state">
                    <strong>No calendar events found.</strong>
                    <span>Connect Google Calendar to see meetings and time blocks alongside your tasks.</span>
                  </div>
                ) : (
                  <div className="calendar-grid">
                    {calendarDays.map((day) => (
                      <div key={dateKey(day.date)} className="calendar-day">
                        <div className="calendar-day-header">
                          <span>{formatDayName(day.date)}</span>
                          <strong>{formatDayNumber(day.date)}</strong>
                        </div>
                        <div className="calendar-timeline">
                          {timelineHours.map((hour) => (
                            <div key={hour} className="timeline-hour">
                              <span>{String(hour).padStart(2, '0')}:00</span>
                            </div>
                          ))}
                          {day.events.length === 0 && <span className="calendar-empty">No events</span>}
                          {day.events.map((event) => (
                            <button
                              key={event.id}
                              type="button"
                              className="calendar-event-block"
                              style={getEventBlockStyle(event)}
                              onClick={() => openEventEditor(event)}
                            >
                              <span>{formatTime(event.start?.dateTime || event.start?.date)}</span>
                              <strong>{event.summary || '(No title)'}</strong>
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </>
          )}

      {editingEvent && (
        <div className="modal-backdrop" role="presentation">
          <form className="event-editor" onSubmit={handleUpdateEvent}>
            <div className="event-editor-header">
              <h3>Edit event</h3>
              <button type="button" onClick={() => setEditingEvent(null)}>Close</button>
            </div>
            <label>
              Title
              <input
                type="text"
                value={editingEvent.summary}
                onChange={(e) => setEditingEvent({ ...editingEvent, summary: e.target.value })}
                required
              />
            </label>
            <label>
              Starts
              <input
                type="datetime-local"
                value={editingEvent.start}
                onChange={(e) => setEditingEvent({ ...editingEvent, start: e.target.value })}
                required
              />
            </label>
            <label>
              Ends
              <input
                type="datetime-local"
                value={editingEvent.end}
                onChange={(e) => setEditingEvent({ ...editingEvent, end: e.target.value })}
                required
              />
            </label>
            <div className="event-editor-actions">
              <button type="button" onClick={() => setEditingEvent(null)}>Cancel</button>
              <button type="submit" disabled={savingEvent}>
                {savingEvent ? 'Saving...' : 'Save'}
              </button>
            </div>
          </form>
        </div>
      )}
        </>
      )}
    </div>
  );
}

export default App;

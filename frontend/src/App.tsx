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

const dateKey = (date: Date) => date.toISOString().slice(0, 10);

const getEventStartDate = (event: Event) => {
  const startValue = event.start?.dateTime || event.start?.date;
  return startValue ? new Date(startValue) : null;
};

function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);

  const API_BASE_URL = import.meta.env.VITE_API_URL || '';

  const [newTask, setNewTask] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchData = async () => {
    try {
      const [tasksRes, eventsRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/tasks`),
        fetch(`${API_BASE_URL}/api/events`)
      ]);
      
      if (tasksRes.ok) setTasks(await tasksRes.json());
      if (eventsRes.ok) setEvents(await eventsRes.json());
    } catch (err) {
      console.error("Failed to fetch data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleAddTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTask.trim()) return;
    
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: newTask, priority: 1, due_string: 'today' })
      });
      
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

  const formatTime = (isoString?: string) => {
    if (!isoString) return 'All Day';
    return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const formatDayName = (date: Date) => date.toLocaleDateString([], { weekday: 'short' });

  const formatDayNumber = (date: Date) => date.toLocaleDateString([], { day: 'numeric', month: 'short' });

  const groupedTasks: TaskGroup[] = taskGroupOrder
    .map((groupKey) => ({
      title: taskGroupLabels[groupKey],
      tasks: tasks.filter((task) => getTaskGroupKey(task.due) === groupKey)
    }))
    .filter((group) => group.tasks.length > 0);

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

  return (
    <div>
      <h1>✨ AI Task Manager</h1>
      
      <form onSubmit={handleAddTask} className="glass-panel" style={{ marginBottom: '2rem', display: 'flex', gap: '1rem' }}>
        <input 
          type="text" 
          value={newTask}
          onChange={(e) => setNewTask(e.target.value)}
          placeholder="What needs to be done today?" 
          style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', padding: '0.8rem', color: 'white' }}
        />
        <button 
          type="submit" 
          disabled={submitting}
          style={{ background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)', border: 'none', borderRadius: '8px', padding: '0.8rem 1.5rem', color: 'white', fontWeight: 'bold', cursor: 'pointer', transition: 'transform 0.2s' }}
        >
          {submitting ? 'Adding...' : 'Add Task'}
        </button>
      </form>
      
      {loading ? (
        <div className="glass-panel" style={{ textAlign: 'center', padding: '3rem' }}>
          <div style={{ animation: 'spin 1s linear infinite', fontSize: '2rem' }}>⏳</div>
          <p style={{ marginTop: '1rem', color: '#9ca3af' }}>Syncing with Todoist & Google Calendar...</p>
        </div>
      ) : (
        <div className="dashboard-grid">
          {/* Todoist Tasks Panel */}
          <section className="glass-panel">
            <h2>🎯 Active Tasks</h2>
            <div className="item-list">
              {tasks.length === 0 ? (
                <p style={{ color: '#9ca3af' }}>No active tasks found.</p>
              ) : (
                groupedTasks.map((group) => (
                  <div key={group.title} className="task-group">
                    <div className="task-group-header">
                      <h3>{group.title}</h3>
                      <span>{group.tasks.length}</span>
                    </div>
                    <div className="task-group-list">
                      {group.tasks.map(task => (
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

          {/* Google Calendar Panel */}
          <section className="glass-panel">
            <h2>📅 Upcoming Events</h2>
            <div className="calendar-grid">
              {events.length === 0 ? (
                <p style={{ color: '#9ca3af' }}>No upcoming events found.</p>
              ) : (
                calendarDays.map((day) => (
                  <div key={dateKey(day.date)} className="calendar-day">
                    <div className="calendar-day-header">
                      <span>{formatDayName(day.date)}</span>
                      <strong>{formatDayNumber(day.date)}</strong>
                    </div>
                    <div className="calendar-events">
                      {day.events.length === 0 ? (
                        <span className="calendar-empty">No events</span>
                      ) : (
                        day.events.map((event) => (
                          <div key={event.id} className="calendar-event">
                            <span>{formatTime(event.start?.dateTime || event.start?.date)}</span>
                            <strong>{event.summary || '(No title)'}</strong>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
      )}
      
      <style>{`
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}

export default App;

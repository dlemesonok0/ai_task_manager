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
}

function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [tasksRes, eventsRes] = await Promise.all([
          fetch('http://localhost:8000/api/tasks'),
          fetch('http://localhost:8000/api/events')
        ]);
        
        if (tasksRes.ok) setTasks(await tasksRes.json());
        if (eventsRes.ok) setEvents(await eventsRes.json());
      } catch (err) {
        console.error("Failed to fetch data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const formatTime = (isoString?: string) => {
    if (!isoString) return 'All Day';
    return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div>
      <h1>✨ AI Task Manager</h1>
      
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
                tasks.map(task => (
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

          {/* Google Calendar Panel */}
          <section className="glass-panel">
            <h2>📅 Upcoming Events</h2>
            <div className="item-list">
              {events.length === 0 ? (
                <p style={{ color: '#9ca3af' }}>No upcoming events found.</p>
              ) : (
                events.map(event => (
                  <div key={event.id} className="item-card event">
                    <div className="item-title">{event.summary || '(No title)'}</div>
                    <div className="item-meta">
                      <span>{formatTime(event.start?.dateTime || event.start?.date)} - {formatTime(event.end?.dateTime || event.end?.date)}</span>
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

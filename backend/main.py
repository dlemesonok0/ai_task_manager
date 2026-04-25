from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .services.todoist_service import todoist_service
from .services.gcal_service import gcal_service

app = FastAPI(
    title="AI Task Manager API",
    description="Backend for the AI Task Manager with Todoist, Google Calendar, and Telegram integrations.",
    version="1.0.0"
)

# Allow CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/tasks")
async def get_tasks():
    tasks = await todoist_service.get_active_tasks()
    return [{"id": t.id, "content": t.content, "priority": t.priority, "due": getattr(t.due, 'string', None) if getattr(t, 'due', None) else None} for t in tasks]

@app.get("/api/events")
def get_events():
    events = gcal_service.get_upcoming_events(max_results=20)
    return events

@app.get("/")
def read_root():
    return {"status": "ok", "message": "AI Task Manager API is running"}

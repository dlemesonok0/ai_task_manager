from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from services.todoist_service import todoist_service
from services.gcal_service import gcal_service

app = FastAPI(
    title="AI Task Manager API",
    description="Backend for the AI Task Manager with Todoist, Google Calendar, and Telegram integrations.",
    version="1.0.0"
)

# Pydantic models for documentation
class TaskCreate(BaseModel):
    content: str
    priority: Optional[int] = 1
    due_string: Optional[str] = "today"

class TaskResponse(BaseModel):
    id: str
    content: str
    priority: int
    due: Optional[str] = None

class CalendarEvent(BaseModel):
    id: str
    summary: Optional[str] = None
    start: dict
    end: dict

# Allow CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/tasks", response_model=List[TaskResponse], tags=["Tasks"])
async def get_tasks():
    """Fetch all active tasks from Todoist."""
    tasks = await todoist_service.get_active_tasks()
    return [{"id": t.id, "content": t.content, "priority": t.priority, "due": getattr(t.due, 'string', None) if getattr(t, 'due', None) else None} for t in tasks]

@app.post("/api/tasks", response_model=TaskResponse, tags=["Tasks"])
async def create_task(task_data: TaskCreate):
    """Create a new task in Todoist."""
    task = await todoist_service.create_task(
        content=task_data.content,
        priority=task_data.priority,
        due_string=task_data.due_string
    )
    if not task:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to create task")
    return {"id": task.id, "content": task.content, "priority": task.priority, "due": getattr(task.due, 'string', None) if getattr(task, 'due', None) else None}


@app.get("/api/events", response_model=List[dict], tags=["Calendar"])
def get_events():
    """Fetch upcoming events from Google Calendar."""
    events = gcal_service.get_upcoming_events(max_results=20)
    return events

@app.get("/", tags=["Health"])
def read_root():
    return {"status": "ok", "message": "AI Task Manager API is running"}

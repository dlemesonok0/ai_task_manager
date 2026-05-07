import logging
import time

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from services.todoist_service import todoist_service
from services.gcal_service import gcal_service
from services.auth_service import authenticate_user, create_access_token, require_auth
from services import db_service
from services.logging_service import bind_extra, configure_logging, log_path, monotonic_ms, read_recent_logs

configure_logging()
logger = logging.getLogger(__name__)

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

class CalendarEventUpdate(BaseModel):
    calendar_id: str = "primary"
    summary: str
    start: str
    end: str

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    username: str

class LogResponse(BaseModel):
    entries: list[dict]

class SyncResponse(BaseModel):
    tasks: int
    events: int
    state: dict[str, dict]


def _task_to_response(task) -> dict:
    return {
        "id": task.id,
        "content": task.content,
        "priority": task.priority,
        "due": getattr(task.due, 'string', None) if getattr(task, 'due', None) else None,
    }


async def sync_tasks_cache() -> list[dict]:
    tasks = await todoist_service.get_active_tasks()
    cached_tasks = [_task_to_response(task) for task in tasks]
    db_service.replace_tasks(cached_tasks)
    logger.info("Synced Todoist tasks into cache", extra=bind_extra(task_count=len(cached_tasks)))
    return cached_tasks


def sync_events_cache() -> list[dict]:
    events = gcal_service.get_upcoming_events(max_results=20)
    db_service.replace_events(events)
    logger.info("Synced calendar events into cache", extra=bind_extra(event_count=len(events)))
    return events


async def sync_all_cache() -> SyncResponse:
    tasks = await sync_tasks_cache()
    events = sync_events_cache()
    return SyncResponse(tasks=len(tasks), events=len(events), state=db_service.get_sync_state())

# Allow CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request, call_next):
    start_time = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    except Exception:
        logger.exception(
            "Unhandled request error",
            extra=bind_extra(
                method=request.method,
                path=request.url.path,
                client=request.client.host if request.client else None,
                duration_ms=monotonic_ms(start_time),
            ),
        )
        raise
    finally:
        logger.info(
            "HTTP request completed",
            extra=bind_extra(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code if response else 500,
                client=request.client.host if request.client else None,
                duration_ms=monotonic_ms(start_time),
            ),
        )

@app.post("/api/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(credentials: LoginRequest):
    if not authenticate_user(credentials.username, credentials.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    return {"access_token": create_access_token(credentials.username), "token_type": "bearer"}

@app.get("/api/auth/me", response_model=UserResponse, tags=["Auth"])
def read_current_user(auth_payload: dict = Depends(require_auth)):
    return {"username": auth_payload["sub"]}

@app.get("/api/logs", response_model=LogResponse, tags=["Logs"], dependencies=[Depends(require_auth)])
def get_logs(limit: int = 200):
    return {"entries": read_recent_logs(limit=limit)}

@app.get("/api/logs/download", tags=["Logs"], dependencies=[Depends(require_auth)])
def download_logs():
    path = log_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")
    return FileResponse(path, media_type="application/jsonl", filename=path.name)

@app.post("/api/sync", response_model=SyncResponse, tags=["Sync"], dependencies=[Depends(require_auth)])
async def sync_data():
    return await sync_all_cache()

@app.get("/api/sync/state", response_model=dict[str, dict], tags=["Sync"], dependencies=[Depends(require_auth)])
def get_sync_state():
    return db_service.get_sync_state()

@app.get("/api/tasks", response_model=List[TaskResponse], tags=["Tasks"], dependencies=[Depends(require_auth)])
async def get_tasks(background_tasks: BackgroundTasks, refresh: bool = False):
    """Fetch all active tasks from Todoist."""
    cached_tasks = db_service.get_tasks()
    if refresh or not cached_tasks:
        cached_tasks = await sync_tasks_cache()
    else:
        background_tasks.add_task(sync_tasks_cache)
    logger.info("Fetched active tasks from cache", extra=bind_extra(task_count=len(cached_tasks)))
    return cached_tasks

@app.post("/api/tasks", response_model=TaskResponse, tags=["Tasks"], dependencies=[Depends(require_auth)])
async def create_task(task_data: TaskCreate):
    """Create a new task in Todoist."""
    task = await todoist_service.create_task(
        content=task_data.content,
        priority=task_data.priority,
        due_string=task_data.due_string
    )
    if not task:
        raise HTTPException(status_code=500, detail="Failed to create task")
    cached_task = _task_to_response(task)
    db_service.upsert_task(cached_task)
    logger.info("Created Todoist task", extra=bind_extra(task_id=task.id, priority=task.priority))
    return cached_task


@app.get("/api/events", response_model=List[dict], tags=["Calendar"], dependencies=[Depends(require_auth)])
def get_events(background_tasks: BackgroundTasks, refresh: bool = False):
    """Fetch upcoming events from Google Calendar."""
    events = db_service.get_events()
    if refresh or not events:
        events = sync_events_cache()
    else:
        background_tasks.add_task(sync_events_cache)
    logger.info("Fetched calendar events from cache", extra=bind_extra(event_count=len(events)))
    return events

@app.patch("/api/events/{event_id}", response_model=dict, tags=["Calendar"], dependencies=[Depends(require_auth)])
def update_event(event_id: str, event_data: CalendarEventUpdate):
    """Update an existing Google Calendar event."""
    from datetime import datetime
    try:
        start_time = datetime.fromisoformat(event_data.start.replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(event_data.end.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid event datetime")
    if end_time <= start_time:
        raise HTTPException(status_code=400, detail="Event end must be after start")

    event = gcal_service.update_event(
        event_id=event_id,
        calendar_id=event_data.calendar_id,
        summary=event_data.summary,
        start_time=start_time,
        end_time=end_time
    )
    if not event:
        raise HTTPException(status_code=500, detail="Failed to update event")
    db_service.upsert_event(event)
    logger.info("Updated calendar event", extra=bind_extra(event_id=event_id, calendar_id=event_data.calendar_id))
    return event

@app.get("/", tags=["Health"])
def read_root():
    return {"status": "ok", "message": "AI Task Manager API is running"}

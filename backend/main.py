import logging
import time

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from services.todoist_service import todoist_service_for_token
from services.gcal_service import gcal_service_for_token
from services.auth_service import authenticate_user_record, create_access_token, register_user, require_auth
from services import db_service
from services.logging_service import bind_extra, configure_logging, log_path, monotonic_ms, read_recent_logs
from services.ai_service import ai_service

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Task Manager API",
    description="Backend for the AI Task Manager with Todoist, Google Calendar, and Telegram integrations.",
    version="1.0.0"
)

@app.on_event("startup")
def initialize_database():
    db_service.init_db()

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

class RegisterRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    username: str

class LogResponse(BaseModel):
    entries: list[dict]

class IntegrationUpdate(BaseModel):
    todoist_api_token: Optional[str] = None
    google_token_json: Optional[str] = None
    telegram_bot_token: Optional[str] = None

class IntegrationStatus(BaseModel):
    todoist_connected: bool
    google_connected: bool
    telegram_connected: bool
    updated_at: Optional[str] = None
    telegram_username: Optional[str] = None
    telegram_linked_at: Optional[str] = None

class TelegramLinkCodeResponse(BaseModel):
    code: str
    expires_at: str
    command: str

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


def current_user_id(auth_payload: dict) -> int:
    return int(auth_payload["uid"])


def user_integrations(user_id: int) -> dict:
    return db_service.get_integrations(user_id, include_secrets=True)


def integration_status(user_id: int) -> dict:
    status_data = db_service.get_integrations(user_id)
    telegram_link = db_service.get_telegram_link(user_id)
    status_data["telegram_connected"] = bool(telegram_link)
    status_data["telegram_username"] = telegram_link.get("telegram_username") if telegram_link else None
    status_data["telegram_linked_at"] = telegram_link.get("linked_at") if telegram_link else None
    return status_data


async def sync_tasks_cache(user_id: int) -> list[dict]:
    integrations = user_integrations(user_id)
    service = todoist_service_for_token(integrations.get("todoist_api_token"))
    tasks = await service.get_active_tasks()
    cached_tasks = [_task_to_response(task) for task in tasks]
    db_service.replace_tasks(user_id, cached_tasks)
    logger.info("Synced Todoist tasks into cache", extra=bind_extra(user_id=user_id, task_count=len(cached_tasks)))
    return cached_tasks


def sync_events_cache(user_id: int) -> list[dict]:
    integrations = user_integrations(user_id)
    service = gcal_service_for_token(integrations.get("google_token_json"))
    events = service.get_upcoming_events(max_results=20)
    db_service.replace_events(user_id, events)
    logger.info("Synced calendar events into cache", extra=bind_extra(user_id=user_id, event_count=len(events)))
    return events


async def sync_all_cache(user_id: int) -> SyncResponse:
    tasks = await sync_tasks_cache(user_id)
    events = sync_events_cache(user_id)
    return SyncResponse(tasks=len(tasks), events=len(events), state=db_service.get_sync_state(user_id))

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
    user = authenticate_user_record(credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    return {"access_token": create_access_token(user["username"], user["id"]), "token_type": "bearer"}

@app.post("/api/auth/register", response_model=TokenResponse, tags=["Auth"])
def register(credentials: RegisterRequest):
    if len(credentials.username.strip()) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(credentials.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    user = register_user(credentials.username.strip(), credentials.password)
    return {"access_token": create_access_token(user["username"], user["id"]), "token_type": "bearer"}

@app.get("/api/auth/me", response_model=UserResponse, tags=["Auth"])
def read_current_user(auth_payload: dict = Depends(require_auth)):
    return {"id": current_user_id(auth_payload), "username": auth_payload["sub"]}

@app.get("/api/integrations", response_model=IntegrationStatus, tags=["Integrations"], dependencies=[Depends(require_auth)])
def get_integrations(auth_payload: dict = Depends(require_auth)):
    return integration_status(current_user_id(auth_payload))

@app.put("/api/integrations", response_model=IntegrationStatus, tags=["Integrations"], dependencies=[Depends(require_auth)])
def update_integrations(integrations: IntegrationUpdate, auth_payload: dict = Depends(require_auth)):
    if integrations.google_token_json:
        try:
            import json
            json.loads(integrations.google_token_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Google token JSON is invalid")
    user_id = current_user_id(auth_payload)
    db_service.upsert_integrations(
        user_id,
        todoist_api_token=integrations.todoist_api_token,
        google_token_json=integrations.google_token_json,
    )
    return integration_status(user_id)

@app.post("/api/telegram/link-code", response_model=TelegramLinkCodeResponse, tags=["Integrations"], dependencies=[Depends(require_auth)])
def create_telegram_link_code(auth_payload: dict = Depends(require_auth)):
    link_code = db_service.create_telegram_link_code(current_user_id(auth_payload))
    return {
        **link_code,
        "command": f"/link {link_code['code']}",
    }

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
async def sync_data(auth_payload: dict = Depends(require_auth)):
    return await sync_all_cache(current_user_id(auth_payload))

@app.get("/api/sync/state", response_model=dict[str, dict], tags=["Sync"], dependencies=[Depends(require_auth)])
def get_sync_state(auth_payload: dict = Depends(require_auth)):
    return db_service.get_sync_state(current_user_id(auth_payload))

@app.get("/api/tasks", response_model=List[TaskResponse], tags=["Tasks"], dependencies=[Depends(require_auth)])
async def get_tasks(background_tasks: BackgroundTasks, refresh: bool = False, auth_payload: dict = Depends(require_auth)):
    """Fetch all active tasks from Todoist."""
    user_id = current_user_id(auth_payload)
    cached_tasks = db_service.get_tasks(user_id)
    if refresh or not cached_tasks:
        cached_tasks = await sync_tasks_cache(user_id)
    else:
        background_tasks.add_task(sync_tasks_cache, user_id)
    logger.info("Fetched active tasks from cache", extra=bind_extra(user_id=user_id, task_count=len(cached_tasks)))
    return cached_tasks

@app.post("/api/tasks", response_model=TaskResponse, tags=["Tasks"], dependencies=[Depends(require_auth)])
async def create_task(task_data: TaskCreate, auth_payload: dict = Depends(require_auth)):
    """Create a new task in Todoist."""
    user_id = current_user_id(auth_payload)
    integrations = user_integrations(user_id)
    service = todoist_service_for_token(integrations.get("todoist_api_token"))
    task = await service.create_task(
        content=task_data.content,
        priority=task_data.priority,
        due_string=task_data.due_string
    )
    if not task:
        raise HTTPException(status_code=500, detail="Failed to create task")
    cached_task = _task_to_response(task)
    db_service.upsert_task(user_id, cached_task)
    logger.info("Created Todoist task", extra=bind_extra(user_id=user_id, task_id=task.id, priority=task.priority))
    return cached_task


@app.get("/api/events", response_model=List[dict], tags=["Calendar"], dependencies=[Depends(require_auth)])
def get_events(background_tasks: BackgroundTasks, refresh: bool = False, auth_payload: dict = Depends(require_auth)):
    """Fetch upcoming events from Google Calendar."""
    user_id = current_user_id(auth_payload)
    events = db_service.get_events(user_id)
    if refresh or not events:
        events = sync_events_cache(user_id)
    else:
        background_tasks.add_task(sync_events_cache, user_id)
    logger.info("Fetched calendar events from cache", extra=bind_extra(user_id=user_id, event_count=len(events)))
    return events

@app.patch("/api/events/{event_id}", response_model=dict, tags=["Calendar"], dependencies=[Depends(require_auth)])
def update_event(event_id: str, event_data: CalendarEventUpdate, auth_payload: dict = Depends(require_auth)):
    """Update an existing Google Calendar event."""
    from datetime import datetime
    try:
        start_time = datetime.fromisoformat(event_data.start.replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(event_data.end.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid event datetime")
    if end_time <= start_time:
        raise HTTPException(status_code=400, detail="Event end must be after start")

    user_id = current_user_id(auth_payload)
    integrations = user_integrations(user_id)
    service = gcal_service_for_token(integrations.get("google_token_json"))
    event = service.update_event(
        event_id=event_id,
        calendar_id=event_data.calendar_id,
        summary=event_data.summary,
        start_time=start_time,
        end_time=end_time
    )
    if not event:
        raise HTTPException(status_code=500, detail="Failed to update event")
    db_service.upsert_event(user_id, event)
    logger.info("Updated calendar event", extra=bind_extra(user_id=user_id, event_id=event_id, calendar_id=event_data.calendar_id))
    return event

@app.get("/", tags=["Health"])
def read_root():
    return {"status": "ok", "message": "AI Task Manager API is running"}

@app.get("/api/health/ai", tags=["Health"])
async def ai_health():
    return await ai_service.health_check()

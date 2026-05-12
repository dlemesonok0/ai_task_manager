import logging
import os
from typing import List, Optional
from todoist_api_python.api_async import TodoistAPIAsync
from todoist_api_python.models import Task
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class TodoistService:
    def __init__(self, token: str | None = None):
        token = token if token is not None else os.getenv("TODOIST_API_TOKEN")
        if not token or token == "your_todoist_token_here":
            self.api = None
            logger.warning("TODOIST_API_TOKEN is not set")
        else:
            self.api = TodoistAPIAsync(token)

    async def get_active_tasks(self) -> List[Task]:
        """Fetch all active tasks from Todoist."""
        if not self.api:
            return []
        try:
            paginator = await self.api.get_tasks()
            if isinstance(paginator, list):
                return paginator
            # AsyncResultsPaginator yields pages (lists of tasks)
            tasks = []
            async for page in paginator:
                tasks.extend(page)
            return tasks
        except Exception:
            logger.exception("Error fetching tasks from Todoist")
            return []

    async def create_task(self, content: str, due_string: Optional[str] = None, priority: int = 1) -> Optional[Task]:
        """Create a new task in Todoist."""
        if not self.api:
            return None
        try:
            task_data = {
                "content": content,
                "priority": priority,
            }
            if due_string:
                task_data["due_string"] = due_string

            task = await self.api.add_task(**task_data)
            return task
        except Exception:
            logger.exception("Error creating task in Todoist")
            return None

    async def create_inbox_task(self, content: str) -> Optional[Task]:
        """Create a task in Todoist Inbox without a due date."""
        return await self.create_task(content=content, due_string=None, priority=1)

    async def close_task(self, task_id: str) -> bool:
        """Close a task by ID."""
        if not self.api:
            return False
        try:
            is_success = await self.api.close_task(task_id=task_id)
            return is_success
        except Exception:
            logger.exception("Error closing task in Todoist")
            return False

# Create a singleton instance
todoist_service = TodoistService()


def todoist_service_for_token(token: str | None) -> TodoistService:
    return TodoistService(token=token)

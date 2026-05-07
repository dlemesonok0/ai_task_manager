import datetime
import logging
from typing import List, Dict, Any
from .todoist_service import todoist_service
from .gcal_service import gcal_service
from .ai_service import ai_service

logger = logging.getLogger(__name__)

class SchedulerService:
    def __init__(self):
        pass

    async def generate_smart_schedule(self) -> List[Dict[str, Any]]:
        """
        Fetches tasks from Todoist and events from Google Calendar,
        then uses AI to propose a schedule by assigning time blocks
        to the tasks in the gaps between events.
        """
        # 1. Get tasks
        tasks = await todoist_service.get_active_tasks()
        if not tasks:
            return []

        # 2. Get today's calendar events
        events = gcal_service.get_upcoming_events(max_results=15)
        
        # We will format this into a prompt for the AI to figure out
        # a good schedule for today.
        prompt = "Here are my tasks for today:\n"
        for t in tasks:
            prompt += f"- {t.content} (Priority: {t.priority})\n"

        prompt += "\nHere are my existing calendar events:\n"
        if not events:
            prompt += "- No existing events.\n"
        for e in events:
            start = e['start'].get('dateTime', e['start'].get('date'))
            end = e['end'].get('dateTime', e['end'].get('date'))
            prompt += f"- {e.get('summary')} from {start} to {end}\n"
            
        prompt += """
        Please create a schedule for today, placing the tasks into free time blocks.
        Assume the working day is from 09:00 to 18:00.
        Return ONLY a JSON array of objects, where each object has:
        - "task_id": (you can omit this, just use the title)
        - "title": Task content
        - "start_time": ISO format string (e.g. 2026-04-26T10:00:00Z)
        - "end_time": ISO format string
        """

        if not ai_service.client:
            logger.warning("AI client not configured, cannot generate smart schedule")
            return []

        try:
            response = await ai_service.client.chat.completions.create(
                model=ai_service.model,
                messages=[
                    {"role": "system", "content": "You are a smart scheduling assistant. Output raw JSON arrays."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )
            
            result_text = response.choices[0].message.content.strip()
            
            if result_text.startswith("```json"):
                result_text = result_text[7:-3].strip()
            elif result_text.startswith("```"):
                result_text = result_text[3:-3].strip()
                
            import json
            schedule = json.loads(result_text)
            return schedule
        except Exception:
            logger.exception("Error generating smart schedule")
            return []

    def apply_schedule_to_calendar(self, schedule: List[Dict[str, Any]]):
        """
        Takes the proposed schedule and inserts it into Google Calendar.
        """
        for item in schedule:
            try:
                start = datetime.datetime.fromisoformat(item['start_time'].replace('Z', '+00:00'))
                end = datetime.datetime.fromisoformat(item['end_time'].replace('Z', '+00:00'))
                # Create event
                gcal_service.create_event(
                    summary=f"Task: {item['title']}",
                    start_time=start,
                    end_time=end,
                    description="Auto-scheduled by AI Task Manager"
                )
            except Exception:
                logger.exception("Failed to schedule item", extra={"_extra": {"title": item.get("title")}})

scheduler_service = SchedulerService()

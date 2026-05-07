import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from dotenv import load_dotenv

from services.ai_service import ai_service
from services.todoist_service import todoist_service
from services.scheduler import scheduler_service
from services.logging_service import configure_logging

load_dotenv()
configure_logging()
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

bot = None
dp = Dispatcher()

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """This handler receives messages with `/start` command"""
    await message.answer(
        f"👋 Привет, {message.from_user.full_name}!\n\n"
        "Я твой персональный AI Task Manager. Я помогу тебе управлять задачами и календарем.\n\n"
        "Просто напиши мне любую задачу, например: *'Купить молоко завтра в 9 утра'*.\n\n"
        "Доступные команды:\n"
        "/briefing — сводка задач на сегодня\n"
        "/autoschedule — умное планирование дня в календаре\n"
        "/help — помощь по использованию"
    )

@dp.message(Command("help"))
async def command_help_handler(message: Message) -> None:
    """Provides help instructions"""
    help_text = (
        "📖 **Как мной пользоваться:**\n\n"
        "1. **Создание задач**: Просто пиши текст. Я пойму время и приоритет.\n"
        "2. **Сводка**: Команда /briefing покажет топ-10 твоих активных задач.\n"
        "3. **Умное планирование**: Команда /autoschedule проанализирует твои задачи и свободное время в Google Календаре, после чего предложит оптимальное расписание и само создаст события.\n\n"
        "Я использую ИИ для понимания твоих намерений, так что можешь общаться со мной на обычном языке!"
    )
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(Command("inbox"))
async def command_inbox_handler(message: Message) -> None:
    """Creates a Todoist Inbox task without AI parsing or due date."""
    command_text = message.text or ""
    task_content = command_text.partition(" ")[2].strip()

    if not task_content:
        await message.answer("Напиши задачу после команды: /inbox купить молоко")
        return

    task = await todoist_service.create_inbox_task(task_content)
    if task:
        await message.answer(f"✅ Added to Inbox: **{task.content}**", parse_mode="Markdown")
    else:
        await message.answer("❌ Failed to create task in Todoist Inbox. Check your API token.")

@dp.message(Command("briefing"))
async def command_briefing_handler(message: Message) -> None:
    """Generates a daily briefing"""
    # Fetch active tasks
    tasks = await todoist_service.get_active_tasks()
    
    if not tasks:
        await message.answer("You have no active tasks for today. Enjoy your day!")
        return

    # Just a simple list for now
    task_list = "\n".join([f"- {t.content} (Priority: {t.priority})" for t in tasks[:10]])
    await message.answer(f"Here is your briefing. You have {len(tasks)} active tasks. Top 10:\n\n{task_list}")

@dp.message(Command("autoschedule"))
async def command_autoschedule_handler(message: Message) -> None:
    """Triggers the AI Smart Time-Blocking"""
    status_msg = await message.answer("🔄 Analyzing tasks and calendar availability...")
    
    schedule = await scheduler_service.generate_smart_schedule()
    if not schedule:
        await status_msg.edit_text("❌ Could not generate a schedule. Ensure you have active tasks and AI configured.")
        return
        
    await status_msg.edit_text("✅ Schedule generated! Applying to Google Calendar...")
    
    # Run synchronously for now
    scheduler_service.apply_schedule_to_calendar(schedule)
    
    schedule_text = "\n".join([f"- {item.get('title')} ({item.get('start_time')} - {item.get('end_time')})" for item in schedule])
    await message.answer(f"🗓️ **Your AI Schedule:**\n\n{schedule_text}", parse_mode="Markdown")

@dp.message()
async def text_handler(message: types.Message) -> None:
    """Handles natural language task creation"""
    user_text = message.text
    
    # Send a thinking message
    processing_msg = await message.answer("🧠 Thinking...")
    
    # 1. Parse using AI
    parsed_task = await ai_service.parse_task_nlp(user_text)
    
    # 2. Add to Todoist
    task = await todoist_service.create_task(
        content=parsed_task.get("content", user_text),
        due_string=parsed_task.get("due_string", "today"),
        priority=parsed_task.get("priority", 1)
    )
    
    # 3. Respond
    if task:
        await processing_msg.edit_text(
            f"✅ Task created: **{task.content}**\n"
            f"📅 Due: {parsed_task.get('due_string')}\n"
            f"🚀 Priority: {parsed_task.get('priority')}",
            parse_mode="Markdown"
        )
    else:
        await processing_msg.edit_text("❌ Failed to create task in Todoist. Check your API token.")

async def main() -> None:
    global bot
    if not TOKEN or TOKEN == "your_telegram_bot_token_here":
        logger.warning("TELEGRAM_BOT_TOKEN is not set. Bot will not start")
        return
        
    bot = Bot(token=TOKEN)
    logger.info("Starting Telegram Bot polling")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

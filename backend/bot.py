import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from dotenv import load_dotenv

from services.ai_service import ai_service
from services.todoist_service import todoist_service_for_token
from services import db_service
from services.logging_service import configure_logging

load_dotenv()
configure_logging()
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

bot = None
dp = Dispatcher()


def _telegram_user(message: Message):
    return getattr(message, "from_user", None)


def _telegram_username(message: Message) -> str | None:
    user = _telegram_user(message)
    username = getattr(user, "username", None)
    return username or getattr(user, "full_name", None)


def _task_to_cache(task) -> dict:
    return {
        "id": task.id,
        "content": task.content,
        "priority": task.priority,
        "due": getattr(task.due, "string", None) if getattr(task, "due", None) else None,
    }


async def _link_telegram_account(message: Message, code: str) -> None:
    user = _telegram_user(message)
    telegram_user_id = getattr(user, "id", None)
    if not telegram_user_id:
        await message.answer("Не удалось определить Telegram user id. Попробуй еще раз позже.")
        return

    linked_user = db_service.consume_telegram_link_code(
        code=code,
        telegram_user_id=int(telegram_user_id),
        telegram_username=_telegram_username(message),
    )
    if not linked_user:
        await message.answer("Код привязки не найден или уже истек. Создай новый код в web-интерфейсе.")
        return

    await message.answer(f"✅ Telegram привязан к аккаунту {linked_user['username']}.")


async def _linked_context(message: Message) -> tuple[int, dict] | None:
    user = _telegram_user(message)
    telegram_user_id = getattr(user, "id", None)
    if not telegram_user_id:
        await message.answer("Не удалось определить Telegram user id. Попробуй еще раз позже.")
        return None

    linked_user = db_service.get_user_by_telegram_id(int(telegram_user_id))
    if not linked_user:
        await message.answer(
            "Сначала привяжи Telegram к web-аккаунту.\n"
            "Открой Integrations в web-интерфейсе, создай код и отправь сюда /link CODE."
        )
        return None

    integrations = db_service.get_integrations(linked_user["id"], include_secrets=True)
    if not integrations.get("todoist_api_token"):
        await message.answer("В web-аккаунте не подключен Todoist. Добавь Todoist API token в Integrations.")
        return None

    return int(linked_user["id"]), integrations


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """This handler receives messages with `/start` command"""
    command_text = message.text or ""
    link_code = command_text.partition(" ")[2].strip()
    if link_code:
        await _link_telegram_account(message, link_code)
        return

    linked_user = None
    user = _telegram_user(message)
    telegram_user_id = getattr(user, "id", None)
    if telegram_user_id:
        linked_user = db_service.get_user_by_telegram_id(int(telegram_user_id))

    link_hint = (
        f"Telegram уже привязан к аккаунту {linked_user['username']}."
        if linked_user
        else "Чтобы привязать Telegram к web-аккаунту, создай код в Integrations и отправь /link CODE."
    )
    await message.answer(
        f"👋 Привет, {message.from_user.full_name}!\n\n"
        "Я системный бот AI Task Manager. Я работаю с задачами только после привязки к твоему web-аккаунту.\n\n"
        f"{link_hint}\n\n"
        "Просто напиши мне любую задачу, например: *'Купить молоко завтра в 9 утра'*.\n\n"
        "Доступные команды:\n"
        "/link CODE — привязать Telegram к web-аккаунту\n"
        "/briefing — сводка задач на сегодня\n"
        "/autoschedule — умное планирование дня в календаре\n"
        "/help — помощь по использованию"
    )

@dp.message(Command("link"))
async def command_link_handler(message: Message) -> None:
    command_text = message.text or ""
    link_code = command_text.partition(" ")[2].strip()
    if not link_code:
        await message.answer("Напиши код после команды: /link ABCD1234")
        return
    await _link_telegram_account(message, link_code)

@dp.message(Command("help"))
async def command_help_handler(message: Message) -> None:
    """Provides help instructions"""
    help_text = (
        "📖 **Как мной пользоваться:**\n\n"
        "1. **Привязка**: В web-интерфейсе открой Integrations, создай код и отправь /link CODE.\n"
        "2. **Создание задач**: Просто пиши текст. Я пойму время и приоритет.\n"
        "2. **Сводка**: Команда /briefing покажет топ-10 твоих активных задач.\n"
        "3. **Умное планирование**: Команда /autoschedule будет доступна после перевода планировщика на пользовательские интеграции.\n\n"
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

    context = await _linked_context(message)
    if not context:
        return
    user_id, integrations = context
    todoist_service = todoist_service_for_token(integrations.get("todoist_api_token"))
    task = await todoist_service.create_inbox_task(task_content)
    if task:
        db_service.upsert_task(user_id, _task_to_cache(task))
        await message.answer(f"✅ Added to Inbox: **{task.content}**", parse_mode="Markdown")
    else:
        await message.answer("❌ Failed to create task in Todoist Inbox. Check your API token.")

@dp.message(Command("briefing"))
async def command_briefing_handler(message: Message) -> None:
    """Generates a daily briefing"""
    context = await _linked_context(message)
    if not context:
        return
    user_id, integrations = context
    todoist_service = todoist_service_for_token(integrations.get("todoist_api_token"))
    tasks = await todoist_service.get_active_tasks()
    db_service.replace_tasks(user_id, [_task_to_cache(task) for task in tasks])
    
    if not tasks:
        await message.answer("You have no active tasks for today. Enjoy your day!")
        return

    # Just a simple list for now
    task_list = "\n".join([f"- {t.content} (Priority: {t.priority})" for t in tasks[:10]])
    await message.answer(f"Here is your briefing. You have {len(tasks)} active tasks. Top 10:\n\n{task_list}")

@dp.message(Command("autoschedule"))
async def command_autoschedule_handler(message: Message) -> None:
    """Triggers the AI Smart Time-Blocking"""
    await message.answer(
        "Autoschedule временно доступен только в web-сценарии. "
        "Telegram не будет запускать планировщик через глобальные env-токены."
    )

@dp.message()
async def text_handler(message: types.Message) -> None:
    """Handles natural language task creation"""
    user_text = message.text
    context = await _linked_context(message)
    if not context:
        return
    user_id, integrations = context
    
    # Send a thinking message
    processing_msg = await message.answer("🧠 Thinking...")
    
    # 1. Parse using AI
    parsed_task = await ai_service.parse_task_nlp(user_text)
    
    # 2. Add to Todoist
    todoist_service = todoist_service_for_token(integrations.get("todoist_api_token"))
    task = await todoist_service.create_task(
        content=parsed_task.get("content", user_text),
        due_string=parsed_task.get("due_string", "today"),
        priority=parsed_task.get("priority", 1)
    )
    
    # 3. Respond
    if task:
        db_service.upsert_task(user_id, _task_to_cache(task))
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

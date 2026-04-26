import asyncio
import os
from dotenv import load_dotenv
from todoist_api_python.api_async import TodoistAPIAsync

load_dotenv()

async def main():
    api = TodoistAPIAsync(os.getenv("TODOIST_API_TOKEN"))
    tasks = await api.get_tasks()
    print(f"Type: {type(tasks)}")
    
    items = []
    if hasattr(tasks, '__aiter__'):
        async for item in tasks:
            items.append(item)
            break # just check the first one
    else:
        items = list(tasks)
        
    if items:
        print(f"First item type: {type(items[0])}")
        print(f"First item content: {items[0]}")

if __name__ == "__main__":
    asyncio.run(main())

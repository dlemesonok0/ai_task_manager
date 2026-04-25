from fastapi import FastAPI

app = FastAPI(
    title="AI Task Manager API",
    description="Backend for the AI Task Manager with Todoist, Google Calendar, and Telegram integrations.",
    version="1.0.0"
)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "AI Task Manager is running"}

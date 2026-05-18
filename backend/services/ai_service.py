import os
import json
import logging
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        # Determine which provider to use based on env variables
        if os.getenv("GEMINI_API_KEY"):
            # Using Gemini via OpenAI SDK compatibility
            self.client = AsyncOpenAI(
                api_key=os.getenv("GEMINI_API_KEY"),
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
            self.model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
            self.provider = "gemini"
            logger.info("AI Service initialized with Google Gemini")

        elif os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != "your_openai_api_key_here":
            self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
            self.provider = "openai"
            logger.info("AI Service initialized with OpenAI")

        elif os.getenv("LLM_BASE_URL"):
            # Using a local model (e.g. Ollama)
            self.client = AsyncOpenAI(
                api_key="ollama",
                base_url=os.getenv("LLM_BASE_URL")
            )
            self.model = os.getenv("LLM_MODEL", "llama3")
            self.provider = "local"
            logger.info("AI Service initialized with local model", extra={"_extra": {"model": self.model}})
        else:
            self.client = None
            self.model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
            self.provider = None
            logger.warning("No LLM configuration found. AI features will be disabled")

    async def parse_task_nlp(self, text: str) -> dict:
        """
        Parses a natural language string into structured task data.
        Returns a dict with 'content', 'due_string', and 'priority' (1-4).
        """
        if not self.client:
            return {"content": text, "due_string": "today", "priority": 1}

        prompt = f"""
        Extract task details from the following text: "{text}"
        Return ONLY a JSON object with the following keys:
        - "content": A clean, concise title for the task.
        - "due_string": A natural language date/time (e.g. "tomorrow at 5pm", "next monday", "today"). If none mentioned, use "today".
        - "priority": An integer from 1 to 4 (4 is urgent/highest, 1 is normal/lowest). Default to 1.
        
        Do not wrap the JSON in markdown code blocks. Return just the raw JSON.
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that parses tasks into JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            result_text = response.choices[0].message.content.strip()
            
            # Clean up potential markdown formatting
            if result_text.startswith("```json"):
                result_text = result_text[7:-3].strip()
            elif result_text.startswith("```"):
                result_text = result_text[3:-3].strip()
                
            return json.loads(result_text)
        except Exception:
            logger.exception("Error parsing NLP task")
            return {"content": text, "due_string": "today", "priority": 1}

    async def health_check(self) -> dict:
        if not self.client:
            return {"status": "disabled"}

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Respond with the word ok."},
                    {"role": "user", "content": "Say ok"},
                ],
                max_tokens=1,
                temperature=0.0,
            )
            return {"status": "ok", "provider": self.provider, "model": self.model}
        except Exception as e:
            return {"status": "degraded", "provider": self.provider, "model": self.model, "error": str(e)}

ai_service = AIService()

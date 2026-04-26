import os
import json
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

class AIService:
    def __init__(self):
        # Determine which provider to use based on env variables
        if os.getenv("GEMINI_API_KEY"):
            # Using Gemini via OpenAI SDK compatibility (Gemini 1.5 Pro/Flash)
            self.client = AsyncOpenAI(
                api_key=os.getenv("GEMINI_API_KEY"),
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
            self.model = "gemini-1.5-flash" # Default fast model
            print("AI Service initialized with Google Gemini")
            
        elif os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != "your_openai_api_key_here":
            self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.model = "gpt-4o-mini"
            print("AI Service initialized with OpenAI")
            
        elif os.getenv("LLM_BASE_URL"):
            # Using a local model (e.g. Ollama)
            self.client = AsyncOpenAI(
                api_key="ollama", # dummy key
                base_url=os.getenv("LLM_BASE_URL")
            )
            self.model = os.getenv("LLM_MODEL", "llama3")
            print(f"AI Service initialized with Local Model ({self.model})")
        else:
            self.client = None
            self.model = "gpt-4o-mini"
            print("WARNING: No LLM configuration found. AI features will be disabled.")

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
        except Exception as e:
            print(f"Error parsing NLP task: {e}")
            return {"content": text, "due_string": "today", "priority": 1}

ai_service = AIService()

from google import genai
from google.genai import types
from configs.settings import settings
from typing import Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

class LLMService:
    client: Optional[genai.Client] = None

    def __init__(self):
        if settings.GEMINI_API_KEY:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        else:
            logger.warning("GEMINI_API_KEY not set. LLM features will be disabled or mocked.")

    async def get_completion(self, prompt: str, system_prompt: str = "You are a helpful assistant.") -> str:
        if not self.client:
            return "LLM_DISABLED"
        
        try:
            # Run the synchronous generate_content in a thread pool to make it async-compatible
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.0
                )
            )
            return response.text
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            # Fallback or re-raise depending on desired behavior. 
            # For now, we'll return an error string so the app doesn't crash.
            return f"Error generating response: {str(e)}"

    def get_llm(self):
        """Returns a LangChain ChatGoogleGenerativeAI instance"""
        from langchain_google_genai import ChatGoogleGenerativeAI
        if not settings.GEMINI_API_KEY:
            return None
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.0
        )

llm_service = LLMService()

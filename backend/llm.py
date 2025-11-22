from openai import AsyncOpenAI
from configs.settings import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class LLMService:
    client: Optional[AsyncOpenAI] = None

    def __init__(self):
        if settings.OPENAI_API_KEY:
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        else:
            logger.warning("OPENAI_API_KEY not set. LLM features will be disabled or mocked.")

    async def get_completion(self, prompt: str, system_prompt: str = "You are a helpful assistant.") -> str:
        if not self.client:
            return "LLM_DISABLED"
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4-turbo-preview", # Or gpt-3.5-turbo
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            raise e

llm_service = LLMService()

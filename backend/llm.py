
from backend.configs.settings import settings
from typing import Optional, List, Any, AsyncIterator, Dict, Union
import logging
import asyncio
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable, RunnableConfig

logger = logging.getLogger(__name__)

class MultiKeyChain(Runnable):
    def __init__(self, llms: List[Any]):
        self.llms = llms
        # Basic validation
        if not self.llms:
            raise ValueError("MultiKeyChain cannot be initialized with empty LLM list")

    def bind_tools(self, tools: Any, **kwargs) -> "MultiKeyChain":
        """Bind tools to all underlying LLMs"""
        bound_llms = [llm.bind_tools(tools, **kwargs) for llm in self.llms]
        return MultiKeyChain(bound_llms)

    async def ainvoke(self, input: Any, config: Optional[RunnableConfig] = None, **kwargs) -> Any:
        errors = []
        for i, llm in enumerate(self.llms):
            try:
                if i > 0:
                    logger.info(f"Fallback: Switching to API Key #{i+1}")
                return await llm.ainvoke(input, config, **kwargs)
            except Exception as e:
                logger.warning(f"Error with API Key #{i+1}: {e}")
                errors.append(e)
        
        raise Exception(f"All API keys failed. Last error: {errors[-1]}")



    async def astream_events(self, input: Any, config: Optional[RunnableConfig] = None, **kwargs) -> AsyncIterator[Any]:
        errors = []
        for i, llm in enumerate(self.llms):
            try:
                if i > 0:
                    logger.info(f"Fallback: Switching to API Key #{i+1}")
                async for event in llm.astream_events(input, config, **kwargs):
                    yield event
                return
            except Exception as e:
                logger.warning(f"Error with API Key #{i+1}: {e}")
                errors.append(e)
        
        raise Exception(f"All API keys failed. Last error: {errors[-1]}")
    
    def invoke(self, input: Any, config: Optional[RunnableConfig] = None, **kwargs) -> Any:
        errors = []
        for i, llm in enumerate(self.llms):
            try:
                if i > 0:
                    logger.info(f"Fallback: Switching to API Key #{i+1}")
                return llm.invoke(input, config, **kwargs)
            except Exception as e:
                logger.warning(f"Error with API Key #{i+1}: {e}")
                errors.append(e)
        raise Exception(f"All API keys failed. Last error: {errors[-1]}")



class LLMService:


    def __init__(self):
        # We prefer using LangChain for agents, but this client is for direct single usage if needed
        self.keys = settings.GEMINI_API_KEYS
        if not self.keys:
            logger.warning("GEMINI_API_KEY(S) not set. LLM features will be disabled.")

    async def get_completion(self, prompt: str, system_prompt: str = "You are a helpful assistant.") -> str:
        llm = self.get_llm()
        if not llm:
            return "LLM_DISABLED"
        
        try:
            # MultiKeyChain or ChatGoogleGenerativeAI supports ainvoke
            from langchain_core.messages import HumanMessage, SystemMessage
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            
            response = await llm.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return f"Error generating response: {str(e)}"

    def get_llm(self):
        """Returns a MultiKeyChain wrapping ChatGoogleGenerativeAI instances"""
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        keys = self.keys
        if not keys:
            return None
            
        llms = []
        for key in keys:
            llms.append(ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                google_api_key=key,
                temperature=0.0,
                max_retries=0 # We handle retries via rotation
            ))
            
        if len(llms) == 1:
            return llms[0]
            
        return MultiKeyChain(llms)

    def reload_keys(self):
        """Reloads keys from global settings"""
        from backend.configs.settings import settings
        self.keys = settings.GEMINI_API_KEYS
        logger.info(f"LLMService keys reloaded. Count: {len(self.keys)}")

llm_service = LLMService()

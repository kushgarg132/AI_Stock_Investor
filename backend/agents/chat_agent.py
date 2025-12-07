from typing import Annotated, List, Dict, Any, TypedDict
import operator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from backend.llm import llm_service
from backend.agents.tools import fetch_news_tool, fetch_stock_info_tool, fetch_price_history_tool
import logging

logger = logging.getLogger(__name__)

class ChatAgent:
    def __init__(self):
        self.llm = llm_service.get_llm()
        if not self.llm:
            logger.warning("ChatAgent: No LLM available (API Key missing?)")
            self.agent = None
            return

        self.tools = [fetch_news_tool, fetch_stock_info_tool, fetch_price_history_tool]
        
        # Use LangGraph's prebuilt ReAct agent for simplicity and robustness
        self.agent = create_react_agent(self.llm, self.tools)

    async def processed_message(self, message: str, history: List[Dict[str, str]] = []) -> str:
        if not self.agent:
            return "I am unable to function because the LLM service is not available. Please check API keys."
            
        # Convert history format if needed, but for now assuming ephemeral stateless or passed history
        # We will create a fresh state with history + new message
        
        messages = []
        for h in history:
            if h.get('role') == 'user':
                messages.append(HumanMessage(content=h.get('content')))
            elif h.get('role') == 'assistant':
                messages.append(AIMessage(content=h.get('content')))
        
        messages.append(HumanMessage(content=message))
        
        # Invoke agent
        # The prebuilt react agent returns a dictionary with 'messages'
        try:
            logger.info(f"ChatAgent receiving: {message}")
            result = await self.agent.ainvoke({"messages": messages})
            
            # The last message should be the AI's final answer
            last_msg = result['messages'][-1]
            return last_msg.content
        except Exception as e:
            logger.error(f"ChatAgent error: {e}")
            return f"I encountered an error processing your request: {str(e)}"

chat_agent = ChatAgent()

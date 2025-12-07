from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging
from backend.agents.chat_agent import chat_agent

router = APIRouter(
    tags=["chat"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)

class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = [] # [{'role': 'user', 'content': '...'}, ...]

from fastapi.responses import StreamingResponse
import json

@router.post("/message")
async def chat_message(request: ChatRequest):
    if not request.message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    async def event_generator():
        try:
            async for event in chat_agent.stream_message(request.message, request.history):
                # SSE format
                if event["type"] == "thinking":
                    yield f"event: thinking\ndata: {json.dumps({'text': event['data']})}\n\n"
                elif event["type"] == "content":
                    yield f"event: content\ndata: {json.dumps({'text': event['data']})}\n\n"
                    
            yield "event: done\ndata: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"Error in chat stream: {e}")
            yield f"event: error\ndata: {json.dumps({'text': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

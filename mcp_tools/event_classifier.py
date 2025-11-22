from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from backend.models import FinancialEvent
from backend.llm import llm_service
import json

router = APIRouter()

class EventClassificationRequest(BaseModel):
    text: str
    date: datetime = datetime.now()

class EventClassificationResponse(BaseModel):
    events: List[FinancialEvent]

@router.post("/events/classify", response_model=EventClassificationResponse)
async def classify_events(request: EventClassificationRequest):
    """
    Detects financial events from text.
    """
    prompt = f"""
    Extract financial events from the following text:
    "{request.text}"
    
    Events to look for: Earnings, Mergers, Acquisitions, Layoffs, Guidance Change, FDA Approval, etc.
    
    Return a JSON list of objects: 
    [{{ "event_type": "...", "description": "...", "symbols": ["AAPL"], "impact_rating": 1-10 }}]
    
    If no events found, return [].
    """
    
    try:
        response = await llm_service.get_completion(
            prompt,
            system_prompt="You are a financial event detector. Return strict JSON."
        )
        
        if response == "LLM_DISABLED":
            return EventClassificationResponse(events=[])
            
        # Clean response
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
            
        data = json.loads(response.strip())
        events = []
        for item in data:
            events.append(FinancialEvent(
                event_type=item["event_type"],
                description=item["description"],
                date=request.date,
                symbols=item.get("symbols", []),
                impact_rating=item.get("impact_rating", 5)
            ))
            
        return EventClassificationResponse(events=events)
        
    except Exception as e:
        print(f"Error classifying events: {e}")
        return EventClassificationResponse(events=[])

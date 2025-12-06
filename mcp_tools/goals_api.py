"""
Goals API Endpoint

Provides access to project goals for the frontend UI.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any
from core.goals_loader import goals_loader
from pathlib import Path

router = APIRouter()


class GoalsResponse(BaseModel):
    primary_objectives: List[str]
    monthly_return_target: float
    max_drawdown_limit: float
    max_position_risk_pct: float
    max_position_size_pct: float
    daily_loss_limit_pct: float
    stop_loss_required: bool
    educational_focus: bool
    raw_content: str


class GoalsUpdateRequest(BaseModel):
    content: str


@router.get("/goals", response_model=GoalsResponse)
async def get_goals():
    """
    Get current project goals for the UI.
    """
    goals = goals_loader.goals
    rules = goals.risk_rules
    targets = goals.performance_targets
    
    return GoalsResponse(
        primary_objectives=goals.primary_objectives,
        monthly_return_target=targets.monthly_return_target,
        max_drawdown_limit=targets.max_drawdown_limit,
        max_position_risk_pct=rules.max_position_risk_pct,
        max_position_size_pct=rules.max_position_size_pct,
        daily_loss_limit_pct=rules.daily_loss_limit_pct,
        stop_loss_required=rules.stop_loss_required,
        educational_focus=goals.educational_focus,
        raw_content=goals.raw_content
    )


@router.post("/goals/reload")
async def reload_goals():
    """
    Reload goals from GOALS.md file.
    Call this after updating the file.
    """
    goals_loader.reload()
    return {"message": "Goals reloaded successfully"}


@router.post("/goals/save")
async def save_goals(request: GoalsUpdateRequest):
    """
    Save updated goals to GOALS.md file.
    """
    goals_path = Path(__file__).parent.parent / "GOALS.md"
    
    try:
        with open(goals_path, 'w', encoding='utf-8') as f:
            f.write(request.content)
        
        # Reload after saving
        goals_loader.reload()
        
        return {"message": "Goals saved successfully"}
    except Exception as e:
        return {"error": str(e)}



@router.get("/goals/summary")
async def get_goals_summary():
    """
    Get a brief summary suitable for LLM prompts.
    """
    return {"summary": goals_loader.get_goals_summary()}


@router.get("/goals/parsed")
async def get_parsed_goals():
    """
    Get goals parsed into title/description pairs for the UI.
    """
    import re
    goals = goals_loader.goals
    content = goals.raw_content
    
    parsed = []
    
    # Parse goals from markdown - look for ### N. Title pattern followed by content
    pattern = r'###\s*\d+\.\s*([^\n]+)\n+(?:\*\*Objective\*\*:\s*)?([^\n#]+(?:\n(?!###)[^\n#]+)*)'
    matches = re.findall(pattern, content)
    
    colors = ['blue', 'green', 'orange', 'purple', 'pink', 'cyan']
    icons = ['Education', 'Growth', 'Shield', 'Target', 'Zap', 'Eye']
    
    for i, (title, description) in enumerate(matches):
        parsed.append({
            "id": i + 1,
            "title": title.strip(),
            "description": description.strip(),
            "color": colors[i % len(colors)],
            "iconName": icons[i % len(icons)]
        })
    
    # Fallback if parsing fails
    if not parsed:
        parsed = [
            {"id": 1, "title": "Educational Focus", "description": "Educate users on algorithmic trading.", "color": "blue", "iconName": "Education"},
            {"id": 2, "title": "Profit Target", "description": "Generate 5% monthly profit.", "color": "green", "iconName": "Growth"},
            {"id": 3, "title": "Risk Management", "description": "Prevent extreme losses.", "color": "orange", "iconName": "Shield"}
        ]
    
    return {"goals": parsed}


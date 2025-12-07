"""
Goals Loader Utility

Reads `GOALS.md` and parses it into structured `Goals` objects.
Used by agents and the backend to stay aligned with user objectives.
"""

import re
import logging
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class RiskRules(BaseModel):
    stop_loss_required: bool = True
    max_position_size_pct: float = 5.0
    daily_loss_limit_pct: float = 2.0
    max_drawdown_limit: float = 10.0
    max_position_risk_pct: float = 1.0

class PerformanceTargets(BaseModel):
    monthly_return_target: float = 5.0
    max_drawdown_limit: float = 10.0
    win_rate_target: float = 60.0
    risk_reward_ratio: str = "2:1"

class Goals(BaseModel):
    primary_objectives: List[str] = []
    performance_targets: PerformanceTargets = PerformanceTargets()
    risk_rules: RiskRules = RiskRules()
    educational_focus: bool = True
    raw_content: str = ""

class GoalsLoader:
    def __init__(self, goals_path: str = "GOALS.md"):
        # Resolve to absolute path relative to project root
        project_root = Path(__file__).parent.parent
        self.goals_path = project_root / goals_path
        self.goals = Goals()
        self.load_goals()

    def load_goals(self):
        """Reads GOALS.md and updates self.goals"""
        if not self.goals_path.exists():
            logger.warning(f"GOALS.md not found at {self.goals_path}")
            return

        try:
            with open(self.goals_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.goals.raw_content = content
                self._parse_content(content)
            logger.info("GOALS.md loaded successfully")
        except Exception as e:
            logger.error(f"Error loading GOALS.md: {e}")

    def reload(self):
        """Force reload of goals"""
        self.load_goals()

    def _parse_content(self, content: str):
        """Parses markdown content into structured fields"""
        # Parse Objectives
        # Look for numbered lists under "Primary Goals"
        objectives = []
        lines = content.split('\n')
        in_goals_section = False
        
        for line in lines:
            if "## 🎯 Primary Goals" in line:
                in_goals_section = True
                continue
            if in_goals_section and line.startswith("##"): # Next section
                in_goals_section = False
            
            if in_goals_section and re.match(r"^### \d+\.", line):
                objectives.append(line.split(".", 1)[1].strip())

        self.goals.primary_objectives = objectives

        # Parse Risk Rules (Simple heuristic fallback)
        if "**NO trade without a stop-loss**" in content:
            self.goals.risk_rules.stop_loss_required = True
        
        # Parse Targets
        if "Month Return" in content and "5%" in content: # Simplified check
            self.goals.performance_targets.monthly_return_target = 5.0

    def get_goals_summary(self) -> str:
        """Returns a concise summary string for LLM system prompts"""
        summary = "PROJECT GOALS:\n"
        for i, obj in enumerate(self.goals.primary_objectives):
            summary += f"{i+1}. {obj}\n"
        
        summary += "\nRISK RULES:\n"
        if self.goals.risk_rules.stop_loss_required:
            summary += "- ALWAYS use Stop Loss\n"
        summary += f"- Max Position Size: {self.goals.risk_rules.max_position_size_pct}%\n"
        
        return summary

# Singleton instance
goals_loader = GoalsLoader()

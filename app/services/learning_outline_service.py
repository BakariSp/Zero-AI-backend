# app/services/learning_outline_service.py

from typing import List
import logging



class LearningPathOutlineService:
    """Service to generate outline-only learning path (titles only, no details)."""

    async def generate_outline(
        self,
        interests: List[str],
        difficulty_level: str = "intermediate",
        estimated_days: int = 30
    ) -> List[str]:
        try:
            from app.services.ai_generator import LearningPathPlannerAgent  # 放进来
            planner_agent = LearningPathPlannerAgent()

            outline = await planner_agent.generate_outline(
                interests=interests,
                difficulty_level=difficulty_level,
                estimated_days=estimated_days
            )
            return outline

        except Exception as e:
            logging.error(f"Error generating learning outline: {e}")
            raise

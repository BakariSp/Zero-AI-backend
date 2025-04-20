# app/services/learning_outline_service.py

from typing import List
import logging
import os
from openai import AzureOpenAI

# Import directly from ai_generator but not the helper function
from app.services.ai_generator import LearningPathPlannerAgent, general_client, GENERAL_DEPLOYMENT

class LearningPathOutlineService:
    """Service to generate outline-only learning path (titles only, no details)."""

    def __init__(self):
        try:
            # Create our own instance instead of using the helper function
            if general_client and GENERAL_DEPLOYMENT:
                self.planner_agent = LearningPathPlannerAgent(
                    client=general_client, 
                    deployment=GENERAL_DEPLOYMENT
                )
                logging.info("Successfully initialized LearningPathOutlineService")
            else:
                logging.error("Missing client or deployment for LearningPathPlannerAgent")
                self.planner_agent = None
        except Exception as e:
            logging.error(f"Failed to initialize LearningPathOutlineService: {e}")
            self.planner_agent = None

    async def generate_outline(
        self,
        interests: List[str],
        difficulty_level: str = "intermediate",
        estimated_days: int = 30
    ) -> List[str]:
        try:
            if not self.planner_agent:
                raise RuntimeError("LearningPathPlannerAgent not initialized. Check Azure OpenAI configuration.")
                
            outline = await self.planner_agent.generate_outline(
                interests=interests,
                difficulty_level=difficulty_level,
                estimated_days=estimated_days
            )
            return outline

        except Exception as e:
            logging.error(f"Error generating learning outline: {e}")
            raise

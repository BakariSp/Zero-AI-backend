from typing import List, Dict, Any
import logging
from app.services.ai_generator import LearningPathPlannerAgent, general_client, GENERAL_DEPLOYMENT

class LearningPathDetailService:
    """
    Service to generate detailed course and section content based on outline titles.
    """

    def __init__(self):
        try:
            # Create our own instance with proper initialization
            if general_client and GENERAL_DEPLOYMENT:
                self.agent = LearningPathPlannerAgent(
                    client=general_client, 
                    deployment=GENERAL_DEPLOYMENT
                )
                logging.info("Successfully initialized LearningPathDetailService")
            else:
                logging.error("Missing client or deployment for LearningPathPlannerAgent")
                self.agent = None
        except Exception as e:
            logging.error(f"Failed to initialize LearningPathDetailService: {e}")
            self.agent = None

    async def generate_from_outline(
        self,
        titles: List[str],
        difficulty_level: str = "intermediate",
        estimated_days: int = 30
    ) -> Dict[str, Any]:
        """
        Generate detailed course and section structure from a list of outline titles.
        """
        try:
            # Check if agent is properly initialized
            if not self.agent:
                raise RuntimeError("LearningPathPlannerAgent not initialized. Check Azure OpenAI configuration.")
                
            titles_str = "\n".join(f"{i+1}. {title}" for i, title in enumerate(titles))

            prompt = f"""
            Given the following list of high-level learning topics:
            {titles_str}

            For each topic, create a course object that includes:
            - title (can be same as topic)
            - brief description
            - estimated_days (average per course: ~{estimated_days // max(len(titles), 1)} days)
            - 3-5 sections, each with:
                - title
                - brief description
                - estimated_days
                - 5-10 keywords for card generation

            Return as a JSON list of course objects:
            [
              {{
                "title": "...",
                "description": "...",
                "estimated_days": ...,
                "sections": [
                  {{
                    "title": "...",
                    "description": "...",
                    "estimated_days": ...,
                    "card_keywords": ["...", "..."]
                  }},
                  ...
                ]
              }},
              ...
            ]
            """
            
            # Use the agent to generate the detailed structure
            # Call the newly added method in the agent
            courses_list = await self.agent.generate_courses_from_titles(
                titles=titles,
                difficulty_level=difficulty_level,
                estimated_days=estimated_days
            )

            # The agent now returns a list of courses directly.
            # Wrap it in the expected dictionary format if needed by the caller.
            # Based on the route `generate_sections_from_titles`, it expects {"courses": [...]}
            result = {"courses": courses_list}

            return result
            
        except Exception as e:
            logging.error(f"Error generating detailed learning path: {e}")
            raise

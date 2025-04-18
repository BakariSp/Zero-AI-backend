from typing import List, Dict, Any
import logging
from app.services.ai_generator import LearningPathPlannerAgent

class LearningPathDetailService:
    """
    Service to generate detailed course and section content based on outline titles.
    """

    def __init__(self):
        self.agent = LearningPathPlannerAgent()

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

            # 调用 ChatCompletion 模型
            response = self.agent.client.chat.completions.create(
                model=self.agent.deployment,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert curriculum designer."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=3000
            )

            content = response.choices[0].message.content.strip()
            data = self.agent._extract_json_from_response(content)

            return {
                "courses": data
            }

        except Exception as e:
            logging.error(f"Error in generate_from_outline: {e}")
            raise

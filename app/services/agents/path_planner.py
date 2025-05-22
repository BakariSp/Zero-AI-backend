import logging
import asyncio
import json
import re
from typing import List, Dict, Any, Union
from openai import AzureOpenAI

# Assuming BaseAgent and client setup might be shared or passed in
# For simplicity here, let's assume client is passed or configured globally/via DI

class PathPlannerAgent:
    def __init__(self, client: Union[AzureOpenAI, Any], deployment: str):
         # Simplified init - real app might use dependency injection
         self.client = client
         self.deployment = deployment
         logging.info("Initializing PathPlannerAgent...")

    def _extract_json_from_response(self, content: str) -> Any:
        """Safely extracts JSON object from AI response content."""
        try:
            # Try parsing directly
            return json.loads(content)
        except json.JSONDecodeError:
            # Look for JSON within markdown code blocks
            match = re.search(r"```json\s*([\s\S]*?)\s*```", content)
            if match:
                try:
                    return json.loads(match.group(1).strip())
                except json.JSONDecodeError:
                    logging.error(f"Failed to parse JSON even within markdown block: {match.group(1)}")
            # Look for JSON starting with { and ending with }
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1 and start < end:
                potential_json = content[start:end+1]
                try:
                    return json.loads(potential_json)
                except json.JSONDecodeError:
                    logging.error(f"Failed to parse potential JSON substring: {potential_json}")

        logging.error(f"Could not extract valid JSON from response content: {content}")
        raise ValueError("AI response did not contain valid JSON.")

    async def _make_completion_request(self, messages: List[Dict], **kwargs):
        """
        Make a completion request using either AzureOpenAI or ZhipuAI client.
        This method abstracts the difference between different client types.
        """
        try:
            # Use asyncio.to_thread for blocking SDK calls if using async FastAPI
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                messages=messages,
                temperature=kwargs.get("temperature", 0.6),
                max_tokens=kwargs.get("max_tokens", 3500),
                model=self.deployment,
                response_format=kwargs.get("response_format", {"type": "json_object"})
            )
            return response
        except Exception as e:
            logging.error(f"Error in completion request: {e}", exc_info=True)
            raise

    # Adapted from LearningPathPlannerAgent.generate_learning_path in ai_generator.py
    # See: app/services/ai_generator.py (startLine: 130, endLine: 226)
    async def generate_path(
        self,
        context: dict # Using context dict as input
    ) -> Dict[str, Any]:
        """Generate the overall learning path structure based on context."""
        interests = context.get("interests", ["general topic"])
        difficulty_level = context.get("difficulty_level", "intermediate")
        estimated_days = context.get("estimated_days", 30)

        interests_str = ", ".join(interests)
        # This prompt asks for the full structure including sections/keywords.
        # The DialoguePlanner might call this and then call course/section generators
        # separately, or this agent could be simplified later.
        prompt = f"""
        Create a complete structured learning path for someone interested in {interests_str}.
        The learning path should be at {difficulty_level} level and designed to be completed in approximately {estimated_days} days.

        The learning path should include:
        1. A title for the learning path
        2. A brief description of the learning path
        3. A category (derived from the interests)
        4. 2-4 courses, each with:
           - A title
           - A brief description
           - An estimated number of days for the course
        5. For each course, 3-5 sections, each with:
           - A title
           - A brief description
           - An estimated number of days for this section
           - 5-10 keyword suggestions for cards (just the keywords)

        Format the response as a single JSON object with the following structure:
        {{
            "learning_path": {{
                "title": "Learning Path Title",
                "description": "Learning path description",
                "category": "Main category from interests",
                "difficulty_level": "{difficulty_level}",
                "estimated_days": {estimated_days}
            }},
            "courses": [
                {{
                    "title": "Course 1 Title",
                    "description": "Course 1 description",
                    "order_index": 1,
                    "estimated_days": 10,
                    "sections": [
                        {{
                            "title": "Section 1 Title",
                            "description": "Section 1 description",
                            "order_index": 1,
                            "estimated_days": 3,
                            "card_keywords": ["Keyword 1", "Keyword 2"]
                        }}
                        // ... more sections
                    ]
                }}
                // ... more courses
            ]
        }}
        Ensure the output is ONLY the JSON object, starting with {{ and ending with }}.
        """
        logging.debug(f"Generating learning path with prompt:\n{prompt}")
        try:
            response = await self._make_completion_request(
                messages=[
                    {"role": "system", "content": "You are an expert curriculum designer who creates detailed learning paths in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=3500,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content.strip()
            logging.debug(f"Raw learning path response:\n{content}")
            data = self._extract_json_from_response(content)
            # TODO: Add validation against expected schema if needed
            return data
        except Exception as e:
            logging.error(f"Error in path planner agent: {e}", exc_info=True)
            raise # Re-raise the exception 
import logging
import asyncio
import re
import json
from typing import List, Dict, Any, Union
from openai import AzureOpenAI # Or AsyncOpenAI

class CourseGeneratorAgent:
    def __init__(self, client: AzureOpenAI, deployment: str):
         self.client = client
         self.deployment = deployment
         logging.info("Initializing CourseGeneratorAgent...")

    def _extract_json_from_response(self, content: str) -> Any:
        """Safely extracts JSON object from AI response content."""
        # (Same implementation as in PathPlannerAgent - consider moving to a shared utility)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"```json\s*([\s\S]*?)\s*```", content)
            if match:
                try: return json.loads(match.group(1).strip())
                except json.JSONDecodeError: pass
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1 and start < end:
                try: return json.loads(content[start:end+1])
                except json.JSONDecodeError: pass
        logging.error(f"Could not extract valid JSON from response content: {content}")
        raise ValueError("AI response did not contain valid JSON.")

    # Based on LearningPathDetailService and generate_courses_from_titles
    # See: app/services/learning_detail_service.py (startLine: 26, endLine: 93)
    # See: app/services/ai_generator.py (startLine: 282, endLine: 324)
    async def generate_course(
        self,
        context: dict # Using context dict
    ) -> Dict[str, Any]:
        """
        Generates detailed course structures (including sections and keywords)
        based on context (e.g., list of course titles).
        """
        titles = context.get("titles", [])
        difficulty_level = context.get("difficulty_level", "intermediate")
        # Estimate days based on number of courses if not provided
        estimated_days = context.get("estimated_days", len(titles) * 7 if titles else 30)

        if not titles:
            # Maybe call generate_course_outline first if titles are missing?
            logging.warning("No titles provided for course generation.")
            return {"courses": []} # Return empty structure

        titles_str = "\n".join(f"- {title}" for title in titles)
        days_per_course = estimated_days // max(len(titles), 1)

        prompt = f"""
        Given the following list of course titles:
        {titles_str}

        For each title, create a detailed course object.
        The overall learning path difficulty is {difficulty_level} and total duration is {estimated_days} days.
        Allocate approximately {days_per_course} days per course.

        Each course object must include:
        - title: The original title provided.
        - description: A brief description of the course content and objectives.
        - estimated_days: An estimated number of days to complete this specific course.
        - sections: A list of 3-5 section objects for this course.

        Each section object must include:
        - title: A concise title for the section.
        - description: A brief description of the section's content.
        - order_index: The sequential order of the section within the course (starting from 1).
        - estimated_days: An estimated number of days for this section.
        - card_keywords: A list of 5-10 relevant keywords suitable for generating flashcards for this section.

        Format the response as a single JSON object containing a key named "courses".
        The value of "courses" should be a JSON list, where each element is a course object adhering to the structure described above.

        Ensure the output is ONLY the JSON object containing the 'courses' list.
        """
        logging.debug(f"Generating courses from titles with prompt:\n{prompt}")
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                messages=[
                    {"role": "system", "content": "You are an expert curriculum designer creating detailed course structures with sections and keywords in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=3000, # Adjust based on number of titles/sections
                model=self.deployment,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content.strip()
            data = self._extract_json_from_response(content)

            # Basic validation
            if isinstance(data, dict) and "courses" in data and isinstance(data["courses"], list):
                 # TODO: Add more detailed schema validation if needed
                 return data # Return the dict containing the "courses" list
            else:
                 logging.error(f"Unexpected JSON structure received for courses: {data}")
                 raise ValueError("AI response for courses missing 'courses' list.")

        except Exception as e:
            logging.error(f"Error generating courses from titles: {e}", exc_info=True)
            raise

    # Based on LearningPathOutlineService and generate_outline
    # See: app/services/learning_outline_service.py (startLine: 30, endLine: 49)
    # See: app/services/ai_generator.py (startLine: 228, endLine: 280)
    async def generate_course_outline(
        self,
        context: dict # Using context dict
    ) -> Dict[str, Any]:
        """Generate a high-level outline (course titles only) based on context."""
        interests = context.get("interests", "general topic")
        difficulty_level = context.get("difficulty_level", "intermediate")
        estimated_days = context.get("estimated_days", 30)
        existing_items = context.get("existing_items", []) # For filtering
        limit = context.get("limit", 5) # Max titles to return

        if isinstance(interests, list):
            interests_str = ", ".join(interests)
        else:
            interests_str = interests

        prompt = f"""
                Create a high-level learning path outline (course titles only) for the topic: "{interests_str}".
                Difficulty: {difficulty_level}, Duration: ~{estimated_days} days.

                Return only a numbered list of potential course titles. Do not include descriptions or any other text. Generate around 7-10 potential titles.

                Format:
                1. Course Title 1
                2. Course Title 2
                ...
                """
        logging.debug(f"Generating course outline with prompt:\n{prompt}")
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates lists of course titles for a learning path."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=500,
                model=self.deployment
            )
            content = response.choices[0].message.content.strip()
            lines = content.split("\n")
            outline = []
            for line in lines:
                 line = line.strip()
                 if not line: continue
                 # Remove leading numbers/periods/spaces
                 cleaned_line = re.sub(r"^\s*\d+\.?\s*", "", line).strip()
                 if cleaned_line:
                    outline.append(cleaned_line)

            # Filter out existing items and limit
            filtered_outline = [title for title in outline if title not in existing_items]
            return {"titles": filtered_outline[:limit]}

        except Exception as e:
            logging.error(f"Error generating course outline: {e}", exc_info=True)
            raise 
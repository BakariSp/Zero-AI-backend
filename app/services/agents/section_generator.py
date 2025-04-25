import logging
import asyncio
import json
import re
from typing import List, Dict, Any
from openai import AzureOpenAI # Or AsyncOpenAI

class SectionGeneratorAgent:
    def __init__(self, client: AzureOpenAI, deployment: str):
         self.client = client
         self.deployment = deployment
         logging.info("Initializing SectionGeneratorAgent...")

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

    async def generate_section(
        self,
        context: dict # Using context dict
    ) -> Dict[str, Any]:
        """
        Generates new sections (title, description, keywords) for a given topic/course context.
        """
        topic = context.get("topic") # The specific topic/title to generate sections for
        course_context = context.get("course_context", "") # Description or title of the course
        num_sections = context.get("num_sections", 3)
        difficulty_level = context.get("difficulty_level", "intermediate")
        existing_sections = context.get("existing_sections", []) # Titles of sections already present

        if not topic:
            raise ValueError("Missing 'topic' in context for section generation.")

        # Prompt needs to be designed to generate *new* sections for an existing topic/course
        prompt = f"""
        You are an expert curriculum designer. Given an existing course context and a specific topic within it, generate {num_sections} relevant *new* section outlines that are distinct from the existing ones.

        Course Context: {course_context}
        Topic to generate sections for: {topic}
        Target Difficulty: {difficulty_level}
        Existing Section Titles (do not repeat these): {', '.join(existing_sections) if existing_sections else 'None'}

        For each new section, provide:
        - title: A concise title for the section.
        - description: A brief description of the section's content.
        - card_keywords: A list of 5-7 relevant keywords for generating flashcards.

        Format the response as a single JSON object containing a key named "sections".
        The value of "sections" should be a JSON list of the generated section objects.

        Example structure:
        {{
            "sections": [
                {{
                    "title": "New Section 1 Title",
                    "description": "...",
                    "card_keywords": ["keywordA", "keywordB", ...]
                }},
                // ... more section objects
            ]
        }}

        Ensure the output is ONLY the JSON object containing the 'sections' list.
        """
        logging.debug(f"Generating sections for topic '{topic}' with prompt:\n{prompt}")
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                messages=[
                    {"role": "system", "content": "You create curriculum section outlines in JSON format, avoiding repetition."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=1500, # Adjust
                model=self.deployment,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content.strip()
            data = self._extract_json_from_response(content)

            if isinstance(data, dict) and "sections" in data and isinstance(data["sections"], list):
                 # TODO: Add validation
                 return data # Return dict containing "sections" list
            else:
                 logging.error(f"Unexpected JSON structure received for sections: {data}")
                 raise ValueError("AI response for sections missing 'sections' list.")
        except Exception as e:
            logging.error(f"Error generating sections for topic '{topic}': {e}", exc_info=True)
            raise 
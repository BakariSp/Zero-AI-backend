import logging
import asyncio
import json
import re
from typing import List, Dict, Any, Optional
from openai import AzureOpenAI # Or AsyncOpenAI
from app.cards.schemas import CardCreate # Assuming schema exists for validation

class CardGeneratorAgent:
    def __init__(self, client: AzureOpenAI, deployment: str):
         self.client = client
         self.deployment = deployment
         logging.info("Initializing CardGeneratorAgent...")

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

    # Based on CardGeneratorAgent.generate_multiple_cards_from_topic
    # See: app/services/ai_generator.py (startLine: 470, endLine: 613)
    async def generate_card(
        self,
        context: dict # Using context dict
    ) -> Dict[str, Any]:
        """Generates multiple flashcards based on context."""
        # Topic/Keywords are the primary input
        topic = context.get("topic") # Could be a section title
        keywords = context.get("keywords", []) # Or specific keywords
        num_cards = context.get("num_cards", 1) # How many cards to generate
        course_title = context.get("course_title")
        difficulty = context.get("difficulty_level", "intermediate")
        broader_context = context.get("broader_context") # Optional extra info

        # Determine the main subject for card generation
        generation_subject = topic if topic else ", ".join(keywords)
        if not generation_subject:
             raise ValueError("Missing 'topic' or 'keywords' in context for card generation.")

        # If specific keywords are given, might adjust num_cards or prompt
        if keywords and not topic:
             num_cards = max(num_cards, len(keywords)) # Generate at least one per keyword?
             generation_subject = f"keywords: {', '.join(keywords)}" # Adjust subject for prompt

        # Build context string for the prompt
        context_parts = []
        if course_title: context_parts.append(f"Course: {course_title}")
        if topic: context_parts.append(f"Section/Topic: {topic}") # Add topic if available
        if broader_context: context_parts.append(f"General Context: {broader_context}")
        context_str = "\n".join(context_parts) if context_parts else "N/A"

        # Using the detailed prompt from ai_generator.py
        prompt = f"""
        You are an expert educational content creator specializing in flashcards.
        Based on the provided subject and context, generate exactly {num_cards} distinct educational flashcards.

        Context:
        {context_str}
        Subject for card generation: "{generation_subject}"
        Number of cards to generate: {num_cards}
        Target Difficulty for all cards: {difficulty}

        Format the response as a single JSON object containing a key named "cards". The value of "cards" should be a JSON list, where each element is a flashcard object.
        Each flashcard object in the list must have the following exact structure and fields:
        {{
            "keyword": "A specific keyword related to the subject for this card.",
            "question": "A clear question related to the keyword.",
            "answer": "A concise and accurate answer to the question.",
            "explanation": "A brief explanation providing more context or detail about the answer.",
            "difficulty": "{difficulty}"
            // Optional: "resources": [{{ "url": "...", "title": "..." }}], "tags": ["..."]
        }}

        Example structure for the final output:
        {{
            "cards": [
                {{ "keyword": "...", "question": "...", "answer": "...", "explanation": "...", "difficulty": "{difficulty}" }},
                // ... (total of {num_cards} card objects)
            ]
        }}

        Ensure the output is ONLY the JSON object containing the 'cards' list. Do not include any introductory text, markdown formatting, or explanations outside the JSON structure. Ensure all {num_cards} requested cards are generated.
        """
        logging.debug(f"Generating {num_cards} cards for subject '{generation_subject}' with prompt:\n{prompt}")
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.deployment,
                messages=[
                    {"role": "system", "content": "You are an expert educational content creator who outputs lists of flashcard data in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=300 * num_cards + 500, # Estimate
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            data = self._extract_json_from_response(content)

            # Validation
            card_list_data = None
            if isinstance(data, dict) and "cards" in data and isinstance(data.get("cards"), list):
                 card_list_data = data["cards"]
            elif isinstance(data, list): # Handle direct list response
                 card_list_data = data
            else:
                 logging.error(f"Unexpected JSON structure for cards: {data}")
                 raise ValueError("AI response for cards not in expected list or {{'cards': list}} format.")

            if not card_list_data:
                logging.warning(f"AI returned empty list for subject '{generation_subject}'")
                return {"cards": []}

            # Validate each card dict against CardCreate schema
            validated_cards_dict = []
            required_fields = ["keyword", "question", "answer", "explanation"]
            for card_dict in card_list_data:
                if not isinstance(card_dict, dict): continue
                card_dict.setdefault('difficulty', difficulty) # Ensure difficulty
                if not all(field in card_dict and card_dict[field] for field in required_fields):
                    logging.warning(f"Skipping card due to missing/empty required fields: {card_dict}")
                    continue
                try:
                    # Validate by attempting to create the Pydantic model
                    CardCreate(**card_dict)
                    validated_cards_dict.append(card_dict) # Append the valid dict
                except Exception as validation_err:
                    logging.warning(f"Skipping card due to validation error: {validation_err}. Data: {card_dict}")

            return {"cards": validated_cards_dict} # Return dict containing list of card dicts

        except Exception as e:
            logging.error(f"Error generating cards for subject '{generation_subject}': {e}", exc_info=True)
            raise 
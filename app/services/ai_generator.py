import os
import logging
from typing import List, Dict, Any, Optional, Union, Tuple
import json
import asyncio
from openai import AzureOpenAI
from dotenv import load_dotenv
import re # Import regex
from app.services.cache import generate_cache_key, get_or_create_cached_data
from app.learning_paths.schemas import LearningPathCreate, CourseSectionCreate
from app.courses.schemas import CourseCreate
from app.cards.schemas import CardCreate
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from app.utils.url_validator import get_valid_resources  # Import the URL validator

# Load environment variables
load_dotenv()

# Configure Azure OpenAI client
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
subscription_key = os.getenv("AZURE_OPENAI_API_KEY")
api_version = "2024-12-01-preview"
deployment = "gpt-4o"  # or your specific deployment name

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=endpoint,
    api_key=subscription_key,
)

# --- General Azure OpenAI Configuration ---
GENERAL_API_KEY = os.getenv("AZURE_OPENAI_KEY")
GENERAL_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
GENERAL_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME") # Deployment for general tasks like path planning
GENERAL_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01") # Or your preferred general API version

general_client = AzureOpenAI(
    api_version=GENERAL_API_VERSION,
    azure_endpoint=GENERAL_ENDPOINT,
    api_key=GENERAL_API_KEY
)

# --- Card Generation Fine-Tuned Model Configuration ---
CARD_API_KEY = os.getenv("CARD_MODEL_AZURE_OPENAI_KEY", GENERAL_API_KEY) # Fallback to general key if not set
CARD_ENDPOINT = os.getenv("CARD_MODEL_AZURE_OPENAI_ENDPOINT", GENERAL_ENDPOINT) # Fallback to general endpoint
CARD_DEPLOYMENT = os.getenv("CARD_MODEL_AZURE_DEPLOYMENT_NAME") # Deployment for fine-tuned card generation
CARD_API_VERSION = os.getenv("CARD_MODEL_AZURE_API_VERSION", GENERAL_API_VERSION) # Add this missing line

card_client = AzureOpenAI(
    api_version=CARD_API_VERSION,
    azure_endpoint=CARD_ENDPOINT,
    api_key=CARD_API_KEY
)

class BaseAgent:
    """Base class for all AI agents"""
    def __init__(self, client: Optional[AzureOpenAI], deployment: Optional[str]):
        if client is None or deployment is None:
             raise ValueError(f"{self.__class__.__name__} requires a valid AzureOpenAI client and deployment name.")
        self.client = client
        self.deployment = deployment
        logging.info(f"Initialized {self.__class__.__name__} with deployment '{self.deployment}'")

    def _extract_json_from_response(self, content: str) -> Any:
        """Extracts JSON object or list from potentially messy AI response."""
        original_content = content # Keep original for logging if needed
        logging.debug(f"Attempting to extract JSON from: {content[:500]}...") # Log input

        try:
            # Try finding JSON within ```json ... ``` blocks
            match = re.search(r"```json\s*([\s\S]*?)\s*```", content, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
                return json.loads(json_str)

            # Try finding JSON starting with { or [ potentially after some text
            json_match = re.search(r"^\s*.*?([{].*|\[.*)", content, re.DOTALL | re.MULTILINE)
            if json_match:
                 potential_json = json_match.group(1)
                 try:
                     # Attempt to parse from the first opening brace/bracket
                     return json.loads(potential_json)
                 except json.JSONDecodeError as e:
                     logging.warning(f"Initial JSON parse failed: {e}. Trying cleanup.")
                     # Attempt to find the last valid closing brace/bracket
                     # This is heuristic and might fail for complex cases
                     open_brackets = 0
                     last_valid_index = -1
                     if potential_json.startswith('['):
                         open_char, close_char = '[', ']'
                     elif potential_json.startswith('{'):
                         open_char, close_char = '{', '}'
                     else:
                         raise ValueError("Response does not start with { or [")

                     for i, char in enumerate(potential_json):
                         if char == open_char:
                             open_brackets += 1
                         elif char == close_char:
                             open_brackets -= 1
                             if open_brackets == 0:
                                 last_valid_index = i
                                 break # Found the matching closer for the first opener

                     if last_valid_index != -1:
                         cleaned_json_str = potential_json[:last_valid_index + 1]
                         try:
                             return json.loads(cleaned_json_str)
                         except json.JSONDecodeError as final_e:
                             logging.error(f"Failed to parse cleaned JSON: {final_e}. Cleaned string: {cleaned_json_str}")
                             raise ValueError(f"Could not extract valid JSON after cleanup: {final_e}") from final_e
                     else:
                         raise ValueError("Could not find matching closing bracket/brace.")


            # If no specific markers, try parsing the whole content directly
            return json.loads(content)

        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode JSON response: {e}. Response content: {content}")
            raise ValueError(f"Invalid JSON response from AI: {e}") from e
        except Exception as e:
            logging.error(f"Error extracting JSON: {e}. Content: {content}")
            raise

class LearningPathPlannerAgent(BaseAgent):
    """Agent responsible for generating complete learning paths with courses and sections"""

    async def generate_learning_path(
        self,
        interests: List[str],
        difficulty_level: str = "intermediate",
        estimated_days: int = 30
    ) -> Dict[str, Any]:
        """Generate a complete learning path with courses and sections"""
        try:
            from app.services.cache import generate_cache_key, get_or_create_cached_data

            cache_params = {
                "interests": sorted(interests),
                "difficulty_level": difficulty_level,
                "estimated_days": estimated_days,
                "version": "1.1" # Increment version if prompt changes significantly
            }
            cache_key = generate_cache_key("learning_path", cache_params)

            async def create_learning_path():
                interests_str = ", ".join(interests)
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
                5. For each course, 3-5 sections, each with:
                   - A title
                   - A brief description
                   - An estimated number of days to complete
                   - 5-10 keyword suggestions for cards (just the keywords, not the full content)

                Format the response as a JSON object with the following structure:
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
                            "estimated_days": 10, // Estimated days for the whole course
                            "sections": [
                                {{
                                    "title": "Section 1 Title",
                                    "description": "Section 1 description",
                                    "order_index": 1,
                                    "estimated_days": 3, // Estimated days for this section
                                    "card_keywords": ["Keyword 1", "Keyword 2", "Keyword 3"]
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
                response = await asyncio.to_thread( # Use asyncio.to_thread for blocking call
                    self.client.chat.completions.create, # Use self.client
                    messages=[
                        {"role": "system", "content": "You are an expert curriculum designer who creates detailed learning paths in JSON format."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.6, # Slightly lower temp for structured output
                    max_tokens=3500, # Adjust as needed
                    model=self.deployment, # Use self.deployment
                    response_format={"type": "json_object"} # Request JSON output
                )

                content = response.choices[0].message.content.strip()
                logging.debug(f"Raw learning path response:\n{content}")
                data = self._extract_json_from_response(content)
                # Add validation here if needed (e.g., using Pydantic models)
                return data

            data, from_cache = await get_or_create_cached_data(cache_key, create_learning_path)
            if from_cache:
                logging.info(f"Retrieved learning path from cache for interests: {interests}")

            return data

        except Exception as e:
            logging.error(f"Error in learning path planner agent: {e}", exc_info=True)
            raise

    async def generate_outline(
        self,
        interests: Union[str, List[str]],
        difficulty_level: str = "intermediate",
        estimated_days: int = 30
    ) -> List[str]:
        """Generate a high-level outline only (section titles)"""
        try:
            if isinstance(interests, list):
                interests_str = ", ".join(interests)
            else:
                interests_str = interests

            prompt = f"""
                    Create a high-level learning path outline (section titles only) for the topic: "{interests_str}".
                    Difficulty: {difficulty_level}, Duration: ~{estimated_days} days.

                    Return only a numbered list of section titles. Do not include descriptions or any other text.

                    Format:
                    1. Section title
                    2. Section title
                    ...
                    """

            response = await asyncio.to_thread( # Use asyncio.to_thread
                self.client.chat.completions.create, # Use self.client
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates structured learning outlines."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=800,
                model=self.deployment # Use self.deployment
            )

            content = response.choices[0].message.content.strip()
            lines = content.split("\n")
            # Improved parsing to handle potential variations
            outline = []
            for line in lines:
                 line = line.strip()
                 if not line:
                     continue
                 # Remove leading numbers, periods, spaces
                 cleaned_line = re.sub(r"^\s*\d+\.?\s*", "", line).strip()
                 if cleaned_line:
                    outline.append(cleaned_line)
            return outline

        except Exception as e:
            logging.error(f"Error generating outline: {e}", exc_info=True)
            raise

    async def generate_courses_from_titles(
        self,
        titles: List[str],
        difficulty_level: str,
        estimated_days: int
    ) -> List[Dict[str, Any]]:
        """
        Generates detailed course and section structures from a list of course titles.
        """
        try:
            titles_str = "\n".join(f"- {title}" for title in titles) # Use simple list format
            num_titles = len(titles)
            avg_days_per_course = estimated_days // max(num_titles, 1)

            prompt = f"""
            You are given {num_titles} course titles:
            {titles_str}

            Your task is to generate a detailed course object for EACH of these {num_titles} titles.
            Each course object must include:
            - title: The exact title from the input list above.
            - description: A brief description relevant to the course title.
            - estimated_days: An estimated number of days for this specific course (aim for around {avg_days_per_course} days).
            - sections: A list of 3-5 section objects for this course, each section object including:
                - title: A relevant title for the section within the course.
                - description: A brief description of the section's content.
                - estimated_days: An estimated number of days for this section (e.g., 1-3 days).
                - card_keywords: A list of 5-10 specific keywords relevant to the section's content.

            The overall learning path is intended for a {difficulty_level} level and should take approximately {estimated_days} total days.

            Return the result ONLY as a single JSON list containing exactly {num_titles} course objects, one for each input title. Ensure the list starts with '[' and ends with ']'. Do not include any introductory text or markdown formatting.

            Example structure for the *complete* JSON list output (if 2 titles were provided):
            [
              {{
                "title": "Title 1 From Input List",
                "description": "Description for course 1.",
                "estimated_days": {avg_days_per_course},
                "sections": [ {{...section data...}}, {{...section data...}} ]
              }},
              {{
                "title": "Title 2 From Input List",
                "description": "Description for course 2.",
                "estimated_days": {avg_days_per_course},
                "sections": [ {{...section data...}}, {{...section data...}} ]
              }}
            ]
            """

            logging.debug(f"Generating course details for {num_titles} titles with prompt:\n{prompt}") # Log num_titles
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                messages=[
                    {"role": "system", "content": "You are an expert curriculum designer. You create detailed course structures including sections and keywords for EACH provided course title, outputting ONLY a valid JSON list containing all results."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                # --- INCREASE MAX TOKENS ---
                max_tokens=3500, # Increased from 2500
                # --- END INCREASE ---
                model=self.deployment,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content.strip()
            logging.debug(f"Raw course details response:\n{content}")
            data = self._extract_json_from_response(content)

            logging.debug(f"Parsed course details data type: {type(data)}")
            if isinstance(data, dict):
                logging.debug(f"Parsed course details dictionary keys: {data.keys()}")


            # --- Validation Section (from previous fix) ---
            if isinstance(data, dict) and isinstance(data.get("courses"), list):
                 logging.debug("AI response was a dict with 'courses' key.")
                 return data["courses"]
            elif isinstance(data, list):
                 logging.debug("AI response was a list.")
                 return data
            elif isinstance(data, dict) and "title" in data and "sections" in data:
                 logging.debug("AI response was a single course dictionary. Wrapping in a list.")
                 return [data]
            else:
                 logging.error(f"AI response for course details was not a list, {{'courses': list}}, or a single course dict. Type: {type(data)}. Data: {data}")
                 raise ValueError("Invalid response format from AI for course details.")
            # --- End Validation Section ---

        except Exception as e:
            logging.error(f"Error generating course details from titles: {e}", exc_info=True)
            raise

class CardGeneratorAgent(BaseAgent):
    """Agent responsible for generating detailed card content from keywords"""
    
    async def generate_card(
        self,
        keyword: str,
        context: Optional[str] = None,
        section_title: Optional[str] = None,
        course_title: Optional[str] = None,
        difficulty: str = "intermediate" # Add difficulty
    ) -> CardCreate:
        """Generate a single card based on keyword and context."""
        try:
            # Base cache key (can be refined if needed)
            cache_params = {
                "keyword": keyword,
                "section_title": section_title,
                "course_title": course_title,
                "difficulty": difficulty,
                "version": "1.2"  # Increment when prompt or validation changes
            }
            if context:
                cache_params["context"] = context[:100]  # Truncate for cache key
            
            cache_key = generate_cache_key("single_card", cache_params)
            
            async def create_card():
                # Build context string
                context_parts = []
                if course_title:
                    context_parts.append(f"Course: {course_title}")
                if section_title:
                    context_parts.append(f"Section: {section_title}")
                if context:
                    context_parts.append(f"Additional context: {context}")
                
                context_str = "\n".join(context_parts) if context_parts else "No additional context provided."
                
                # Create the prompt
                prompt = f"""
                Create a high-quality educational flashcard about the keyword: "{keyword}".
                
                Context information:
                {context_str}
                
                The card should be at {difficulty} level difficulty.
                
                Please format your response as a JSON object with the following structure:
                {{
                    "keyword": "{keyword}",
                    "question": "A clear question related to {keyword}",
                    "answer": "A concise and accurate answer to the question",
                    "explanation": "A more detailed explanation that provides additional context or examples",
                    "difficulty": "{difficulty}",
                    "resources": [
                        {{ "url": "https://example.com/resource1", "title": "Resource 1 Title" }},
                        {{ "url": "https://example.com/resource2", "title": "Resource 2 Title" }}
                    ]
                }}
                
                Ensure the URLs in your resources are real, valid URLs to existing web pages. Prefer academic sources, documentation, or authoritative websites when possible.
                """
                
                logging.debug(f"Generating card for keyword '{keyword}' with prompt:\n{prompt}")
                
                # Call Azure OpenAI
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=self.deployment,
                    messages=[
                        {"role": "system", "content": "You are an expert educational content creator who creates high-quality flashcards with accurate resources."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1000,
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
                logging.debug(f"Raw card response:\n{content}")
                
                # Parse the response
                card_data = self._extract_json_from_response(content)
                
                # Validate URLs and get better resources if needed
                if "resources" in card_data:
                    # Validate and enhance resources
                    validated_resources = await asyncio.to_thread(
                        get_valid_resources,
                        keyword=keyword,
                        context=context or section_title,
                        existing_resources=card_data["resources"]
                    )
                    
                    # Update the card with validated resources
                    card_data["resources"] = validated_resources
                else:
                    # If no resources provided, get some
                    card_data["resources"] = await asyncio.to_thread(
                        get_valid_resources,
                        keyword=keyword,
                        context=context or section_title
                    )
                
                # Create a CardCreate object
                return CardCreate(**card_data)
            
            # Get from cache or create
            card_data, from_cache = await get_or_create_cached_data(cache_key, create_card)
            if from_cache:
                logging.info(f"Retrieved card for keyword '{keyword}' from cache")
            
            return card_data
            
        except Exception as e:
            logging.error(f"Error generating card for keyword '{keyword}': {e}", exc_info=True)
            raise

    async def generate_multiple_cards_from_topic(
        self,
        topic: str,
        num_cards: int,
        course_title: Optional[str] = None,
        difficulty: str = "intermediate"
    ) -> List[CardCreate]:
        """Generate multiple distinct cards related to a central topic."""
        logging.info(f"Generating {num_cards} cards for topic: '{topic}' (Course: {course_title}, Difficulty: {difficulty}) using deployment '{self.deployment}'")
        # --- Cache versioning ---
        cache_params = {
            "topic": topic,
            "num_cards": num_cards,
            "difficulty": difficulty,
            "course": course_title,
            "version": "1.3" # Incremented version due to prompt change
        }
        cache_key = generate_cache_key("cards_from_topic", cache_params)
        # --- End Cache versioning ---

        async def create_cards():
            context_parts = []
            if course_title:
                context_parts.append(f"Course Context: {course_title}")
            # Keep difficulty as it's a variable parameter
            context_parts.append(f"Target Difficulty: {difficulty}")
            context_str = "\n".join(context_parts) + "\n\n" if context_parts else ""

            # --- Detailed Prompt for General Model ---
            prompt = f"""
            You are an expert educational content creator specializing in flashcards.
            Based on the provided topic and context, generate exactly {num_cards} distinct educational flashcards.

            Context:
            {context_str}
            Topic: "{topic}"
            Number of cards to generate: {num_cards}
            Target Difficulty for all cards: {difficulty}

            Format the response as a single JSON object containing a key named "cards". The value of "cards" should be a JSON list, where each element is a flashcard object.
            Each flashcard object in the list must have the following exact structure and fields:
            {{
                "keyword": "A specific keyword related to the topic for this card.",
                "question": "A clear question related to the keyword.",
                "answer": "A concise and accurate answer to the question.",
                "explanation": "A brief explanation providing more context or detail about the answer.",
                "difficulty": "{difficulty}", // Should match the target difficulty
                "resources": [{{ "url": "valid_url", "title": "Resource Title" }}] // REQUIRED list of relevant resource URLs and titles
            }}

            Example structure for the final output:
            {{
                "cards": [
                    {{ "keyword": "...", "question": "...", "answer": "...", "explanation": "...", "difficulty": "{difficulty}", "resources": [{{"url": "...", "title": "..."}}] }}, 
                    {{ "keyword": "...", "question": "...", "answer": "...", "explanation": "...", "difficulty": "{difficulty}", "resources": [{{"url": "...", "title": "..."}}] }} 
                    // ... (total of {num_cards} card objects)
                ]
            }}

            Ensure the output is ONLY the JSON object containing the 'cards' list, starting with {{ and ending with }}. Do not include any introductory text, markdown formatting, or explanations outside the JSON structure. Ensure all {num_cards} requested cards are generated.
            """
            # --- End Detailed Prompt ---

            logging.debug(f"Generating multiple cards with detailed prompt:\n{prompt}")
            try:
                response = await asyncio.to_thread( # Use asyncio.to_thread
                    self.client.chat.completions.create, # Use self.client
                    model=self.deployment, # Use self.deployment
                    messages=[
                        # System message is still useful
                        {"role": "system", "content": "You are an expert educational content creator who outputs lists of flashcard data in JSON format."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7, # Adjust temperature as needed
                    max_tokens=300 * num_cards + 500, # Adjusted token estimate slightly
                    response_format={"type": "json_object"} # Still request JSON
                )
                content = response.choices[0].message.content
                logging.debug(f"Raw AI response for topic '{topic}':\n---\n{content}\n---")
                extracted_json = self._extract_json_from_response(content)
                logging.debug(f"Extracted JSON type for topic '{topic}': {type(extracted_json)}")
                logging.debug(f"Extracted JSON content (first 500 chars): {str(extracted_json)[:500]}") # Log the actual extracted data

                # --- Keep Robust Validation ---
                card_list_data = None # Initialize to None
                if isinstance(extracted_json, dict) and "cards" in extracted_json and isinstance(extracted_json.get("cards"), list):
                     logging.debug(f"Validation: Found 'cards' key with a list for topic '{topic}'.")
                     card_list_data = extracted_json["cards"]
                elif isinstance(extracted_json, dict) and "flashcards" in extracted_json and isinstance(extracted_json.get("flashcards"), list):
                     logging.debug(f"Validation: Found 'flashcards' key with a list for topic '{topic}'.")
                     card_list_data = extracted_json["flashcards"] # Extract from 'flashcards' key
                elif isinstance(extracted_json, list):
                     logging.debug(f"Validation: Extracted JSON is a direct list for topic '{topic}'.")
                     card_list_data = extracted_json
                else:
                     # Log the problematic data before raising
                     logging.error(f"Validation failed for topic '{topic}'. Extracted JSON type: {type(extracted_json)}. Value: {extracted_json}")
                     # Update the error message slightly to reflect the accepted formats
                     raise ValueError("Fine-tuned model response was not in the expected list, {'cards': list}, or {'flashcards': list} format.") # Updated error message

                if not card_list_data:
                    logging.warning(f"Fine-tuned model returned an empty list of cards for topic '{topic}'.")
                    return []

                validated_cards = []
                required_fields = ["keyword", "question", "answer", "explanation"]
                for i, card_dict in enumerate(card_list_data):
                    if not isinstance(card_dict, dict):
                        logging.warning(f"Skipping item {i} in list for topic '{topic}' as it's not a dictionary. Item: {card_dict}")
                        continue

                    if not all(field in card_dict for field in required_fields):
                         logging.warning(f"Skipping card from fine-tuned model due to missing required fields for topic '{topic}'. Required: {required_fields}. Data: {card_dict}")
                         continue
                    try:
                        card_dict['difficulty'] = card_dict.get('difficulty', difficulty)
                        validated_cards.append(CardCreate(**card_dict))

                    except Exception as validation_err:
                        logging.warning(f"Skipping card due to validation error for topic '{topic}': {validation_err}. Data: {card_dict}")

                logging.info(f"Successfully validated {len(validated_cards)} cards out of {len(card_list_data)} received for topic '{topic}'.")
                return [card.dict() for card in validated_cards] # Return list of dicts for caching

            except Exception as e:
                logging.error(f"Error generating cards for topic '{topic}': {e}", exc_info=True)
                raise

        # Get from cache or create
        data, from_cache = await get_or_create_cached_data(cache_key, create_cards) # Pass updated key

        if from_cache:
            logging.info(f"Retrieved {len(data)} cards from cache for topic: {topic}")
        else:
             logging.info(f"Generated {len(data)} new cards for topic: {topic}")

        # Ensure data is parsed back into CardCreate objects AFTER retrieving/generating
        try:
            return [CardCreate(**item) for item in data]
        except Exception as e:
             logging.error(f"Failed to parse final CardCreate objects for key {cache_key}: {e}. Data: {data}", exc_info=True)
             return []

    async def generate_cards_for_section_batch(self, section_topic: str, num_cards: int) -> List[Dict[str, Any]]:
        """
        Generates a batch of cards for a given section topic.
        (This is a placeholder - implement the actual logic using self.client)
        """
        logging.info(f"Generating {num_cards} cards for section: {section_topic}")
        # --- Add your actual OpenAI call and JSON parsing logic here ---
        # Example structure of what it might return:
        generated_cards = []
        for i in range(num_cards):
            # Simulate generation
            await asyncio.sleep(0.1) # Simulate async work
            generated_cards.append({
                "keyword": f"{section_topic} Keyword {i+1}",
                "question": f"What is {section_topic} Keyword {i+1}?",
                "answer": f"This is the answer for {section_topic} Keyword {i+1}.",
                "explanation": f"Detailed explanation for {section_topic} Keyword {i+1}.",
                "difficulty": "medium"
            })
        logging.info(f"Finished generating cards for section: {section_topic}")
        return generated_cards

class ParallelCardGeneratorManager:
    """Manager for generating multiple cards in parallel"""
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        # Instantiate CardGeneratorAgent with the card-specific client and deployment
        # Ensure card_client and CARD_DEPLOYMENT are accessible here or passed in
        if card_client and CARD_DEPLOYMENT:
             self.card_generator = CardGeneratorAgent(client=card_client, deployment=CARD_DEPLOYMENT)
        else:
             logging.error("CardGeneratorAgent could not be initialized in ParallelCardGeneratorManager due to missing client/deployment.")
             # Handle this error state appropriately - maybe raise an exception?
             self.card_generator = None # Or provide a dummy agent

    async def generate_cards_for_section(
        self,
        keywords: List[str],
        section_title: str,
        course_title: str,
        difficulty: str # Add difficulty
    ) -> List[CardCreate]:
        """Generate multiple cards in parallel for a section using keywords"""
        if not self.card_generator:
             logging.error("Card generator not available in ParallelCardGeneratorManager.")
             return []

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def _generate_with_semaphore(keyword: str) -> Optional[CardCreate]:
            async with semaphore:
                try:
                    # Use the generate_card method (which now accepts difficulty)
                    return await self.card_generator.generate_card(
                        keyword=keyword,
                        section_title=section_title,
                        course_title=course_title,
                        difficulty=difficulty # Pass difficulty
                    )
                except Exception as e:
                    logging.error(f"Failed to generate card for keyword '{keyword}' in parallel: {e}", exc_info=True)
                    return None # Return None on failure for this specific card

        tasks = [_generate_with_semaphore(keyword) for keyword in keywords]
        results = await asyncio.gather(*tasks)
        # Filter out None results (failures)
        successful_cards = [card for card in results if card is not None]
        logging.info(f"Successfully generated {len(successful_cards)} out of {len(keywords)} cards in parallel for section '{section_title}'.")
        return successful_cards

class LearningAssistantAgent(BaseAgent):
    """Agent responsible for answering user questions and generating related cards during learning"""
    
    async def answer_question(
        self,
        user_query: str,
        current_card_data: Optional[Dict[str, Any]] = None,
        section_title: Optional[str] = None,
        course_title: Optional[str] = None,
        difficulty_level: str = "intermediate"
    ) -> Dict[str, Any]:
        """
        Answers a user question and generates a related card
        
        Args:
            user_query: The user's question or prompt
            current_card_data: Data about the card the user is currently viewing
            section_title: Title of the current section
            course_title: Title of the current course
            difficulty_level: Difficulty level for generated content
            
        Returns:
            Dict with answer to question and a related card
        """
        try:
            # Build context for the prompt
            context_parts = []
            if current_card_data:
                card_context = (
                    f"Current Card: {current_card_data.get('keyword')}\n"
                    f"Question: {current_card_data.get('question')}\n"
                    f"Answer: {current_card_data.get('answer')}\n"
                )
                context_parts.append(card_context)
            
            if course_title:
                context_parts.append(f"Course: {course_title}")
            if section_title:
                context_parts.append(f"Section: {section_title}")
                
            context_str = "\n".join(context_parts) if context_parts else ""
            
            # Create cache key to avoid redundant computations
            cache_params = {
                "query": user_query,
                "card_keyword": current_card_data.get("keyword") if current_card_data else None,
                "section": section_title,
                "course": course_title,
                "difficulty": difficulty_level,
                "version": "1.0"  # Increment if prompt changes
            }
            cache_key = generate_cache_key("learning_assistant", cache_params)
            
            async def generate_response():
                prompt = f"""
                You are an educational assistant helping a user who is currently studying.
                
                CONTEXT:
                {context_str}
                
                USER QUERY:
                {user_query}
                
                Please provide:
                1. A direct, helpful response to the user's question (be accurate and educational)
                2. A related flashcard that would help deepen understanding of this topic
                
                Format your entire response as a single JSON object with these fields:
                {{
                    "answer": "Your direct answer to the user's query. Be thorough but concise.",
                    "related_card": {{
                        "keyword": "A specific keyword related to the user's query but different from the current card",
                        "question": "A clear question related to the keyword",
                        "answer": "A concise and accurate answer to the question",
                        "explanation": "A brief explanation providing more context or detail about the answer",
                        "difficulty": "{difficulty_level}",
                        "resources": [{{ "url": "valid_url", "title": "Resource Title" }}]
                    }}
                }}
                
                Ensure your answer is educational, accurate, and helpful. The related card should explore a concept connected to the user's query but shouldn't duplicate the current card's content.
                """
                
                logging.debug(f"Generating learning assistant response with prompt:\n{prompt}")
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    messages=[
                        {"role": "system", "content": "You are an expert educational assistant who helps users understand concepts and provides related information in JSON format."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1500,
                    model=self.deployment,
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content.strip()
                logging.debug(f"Raw learning assistant response:\n{content}")
                data = self._extract_json_from_response(content)
                
                # Validate response structure
                if not isinstance(data, dict):
                    raise ValueError(f"Expected dict response, got {type(data)}")
                
                if "answer" not in data:
                    raise ValueError("Missing 'answer' field in response")
                
                if "related_card" not in data or not isinstance(data["related_card"], dict):
                    raise ValueError("Missing or invalid 'related_card' field in response")
                
                # Validate the card
                card_data = data["related_card"]
                required_fields = ["keyword", "question", "answer", "explanation"]
                if not all(field in card_data for field in required_fields):
                    logging.warning(f"Card missing required fields. Required: {required_fields}. Card: {card_data}")
                    # Create placeholder card if missing fields
                    data["related_card"] = {
                        "keyword": card_data.get("keyword", "Related Topic"),
                        "question": card_data.get("question", "What is this related topic?"),
                        "answer": card_data.get("answer", "This is a related concept."),
                        "explanation": card_data.get("explanation", "This relates to the current topic."),
                        "difficulty": card_data.get("difficulty", difficulty_level),
                        "resources": card_data.get("resources", [])
                    }
                
                return data
            
            # Get from cache or create
            data, from_cache = await get_or_create_cached_data(cache_key, generate_response)
            
            if from_cache:
                logging.info(f"Retrieved learning assistant response from cache for query: {user_query[:50]}...")
            
            return data
        
        except Exception as e:
            logging.error(f"Error in learning assistant agent: {e}", exc_info=True)
            # Return a fallback response instead of raising to avoid breaking the user experience
            return {
                "answer": f"I'm sorry, I encountered an error while processing your question. Please try rephrasing or asking something else.",
                "related_card": {
                    "keyword": "Error Recovery",
                    "question": "What should I do if the assistant can't answer my question?",
                    "answer": "Try rephrasing your question or breaking it into smaller, more specific questions.",
                    "explanation": "Complex or ambiguous questions might be difficult to process. Simpler, clearer questions often work better.",
                    "difficulty": difficulty_level,
                    "resources": []
                }
            }

    async def generate_related_card(
        self, 
        keyword: str,
        context: Optional[str] = None,
        section_title: Optional[str] = None,
        course_title: Optional[str] = None,
        difficulty_level: str = "intermediate"
    ) -> Dict[str, Any]:
        """
        Generates a single card related to a specific keyword or topic.
        This is a streamlined version that just returns the card data without additional context.
        
        Args:
            keyword: The keyword or topic to generate a card for
            context: Additional context to guide generation
            section_title: Current section title
            course_title: Current course title
            difficulty_level: Desired difficulty level
            
        Returns:
            Dictionary with card data suitable for CardCreate
        """
        try:
            # Try to use CardGeneratorAgent if available
            if card_agent:
                card_data = await card_agent.generate_card(
                    keyword=keyword,
                    context=context,
                    section_title=section_title,
                    course_title=course_title,
                    difficulty=difficulty_level
                )
                if isinstance(card_data, dict):
                    return card_data
                else:
                    # Convert from CardCreate object if needed
                    return card_data.dict()
            
            # Fallback to direct generation if card_agent not available
            cache_params = {
                "keyword": keyword,
                "context": context,
                "section": section_title,
                "course": course_title,
                "difficulty": difficulty_level,
                "version": "1.0"
            }
            cache_key = generate_cache_key("related_card", cache_params)
            
            async def create_card():
                context_parts = []
                if course_title:
                    context_parts.append(f"Course: {course_title}")
                if section_title:
                    context_parts.append(f"Section: {section_title}")
                if context:
                    context_parts.append(f"Context: {context}")
                context_str = "\n".join(context_parts) + "\n\n" if context_parts else ""
                
                prompt = f"""
                You are an expert educational content creator specializing in flashcards.
                Based on the provided keyword and context, generate a single educational flashcard.
                
                Context:
                {context_str}
                Keyword: "{keyword}"
                Target Difficulty: {difficulty_level}
                
                Format the response as a single JSON object with the following exact structure and fields:
                {{
                    "keyword": "{keyword}",
                    "question": "A clear question related to the keyword.",
                    "answer": "A concise and accurate answer to the question.",
                    "explanation": "A brief explanation providing more context or detail about the answer.",
                    "difficulty": "{difficulty_level}",
                    "resources": [{{ "url": "valid_url", "title": "Resource Title" }}]
                }}
                
                Ensure the output is ONLY the JSON object, starting with {{ and ending with }}.
                """
                
                logging.debug(f"Generating related card with prompt:\n{prompt}")
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    messages=[
                        {"role": "system", "content": "You are an expert educational content creator who outputs flashcard data in JSON format."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1000,
                    model=self.deployment,
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content.strip()
                data = self._extract_json_from_response(content)
                
                # Ensure required fields
                required_fields = ["keyword", "question", "answer", "explanation"]
                if not isinstance(data, dict) or not all(field in data for field in required_fields):
                    logging.error(f"Response missing required fields for keyword '{keyword}'. Data: {data}")
                    raise ValueError("Response missing required fields or not a dict.")
                
                # Ensure difficulty is set
                data['difficulty'] = data.get('difficulty', difficulty_level)
                
                # Ensure resources is a list
                if "resources" not in data or not isinstance(data["resources"], list):
                    data["resources"] = []
                
                return data
            
            # Get from cache or create
            data, from_cache = await get_or_create_cached_data(cache_key, create_card)
            
            if from_cache:
                logging.info(f"Retrieved related card from cache for keyword: {keyword}")
            
            return data
            
        except Exception as e:
            logging.error(f"Error generating related card: {e}", exc_info=True)
            # Return a minimal valid card as fallback
            return {
                "keyword": keyword,
                "question": f"What is {keyword}?",
                "answer": f"This is a concept related to {section_title if section_title else 'the current topic'}.",
                "explanation": "More information would normally be provided here.",
                "difficulty": difficulty_level,
                "resources": []
            }

# Initialize the global learning assistant agent
learning_assistant_agent = None

# Try to initialize the learning assistant agent
try:
    if general_client and GENERAL_DEPLOYMENT:
        learning_assistant_agent = LearningAssistantAgent(
            client=general_client, 
            deployment=GENERAL_DEPLOYMENT
        )
        logging.info("Successfully initialized global LearningAssistantAgent")
    else:
        logging.warning("Could not initialize global LearningAssistantAgent: missing client or deployment")
except Exception as e:
    logging.error(f"Error initializing global LearningAssistantAgent: {e}")

# Helper function to get the learning assistant agent
def get_learning_assistant_agent() -> LearningAssistantAgent:
    if not learning_assistant_agent:
        raise RuntimeError("LearningAssistantAgent not initialized. Check Azure OpenAI configuration.")
    return learning_assistant_agent

# Legacy wrapper for backwards compatibility
async def answer_learning_question(
    user_query: str,
    current_card_data: Optional[Dict[str, Any]] = None,
    section_title: Optional[str] = None,
    course_title: Optional[str] = None,
    difficulty_level: str = "intermediate"
) -> Dict[str, Any]:
    """Legacy wrapper for answering user questions during learning"""
    if not learning_assistant_agent:
        raise RuntimeError("LearningAssistantAgent not initialized. Check Azure OpenAI configuration.")
    return await learning_assistant_agent.answer_question(
        user_query=user_query,
        current_card_data=current_card_data,
        section_title=section_title,
        course_title=course_title,
        difficulty_level=difficulty_level
    )

# --- Legacy function wrappers ---
# Consider refactoring code that uses these to instantiate agents directly
# or use a dependency injection framework.

# Global agent instances with improved error handling
learning_path_agent = None
card_agent = None

# Initialize the agents if possible
try:
    if general_client and GENERAL_DEPLOYMENT:
        learning_path_agent = LearningPathPlannerAgent(
            client=general_client, 
            deployment=GENERAL_DEPLOYMENT
        )
        logging.info("Successfully initialized global LearningPathPlannerAgent")
    else:
        logging.warning("Could not initialize global LearningPathPlannerAgent: missing client or deployment")
except Exception as e:
    logging.error(f"Error initializing global LearningPathPlannerAgent: {e}")

try:
    if card_client and CARD_DEPLOYMENT:
        card_agent = CardGeneratorAgent(client=card_client, deployment=CARD_DEPLOYMENT)
        logging.info("Successfully initialized global CardGeneratorAgent")
    else:
        logging.warning("Could not initialize global CardGeneratorAgent: missing client or deployment")
except Exception as e:
    logging.error(f"Error initializing global CardGeneratorAgent: {e}")


async def generate_learning_path_with_ai(
    interests: List[str],
    difficulty_level: str = "intermediate",
    estimated_days: int = 30
) -> Dict[str, Any]:
    """Legacy wrapper for backwards compatibility"""
    if not learning_path_agent:
        raise RuntimeError("LearningPathPlannerAgent not initialized. Check Azure OpenAI configuration.")
    # The original implementation here seemed to duplicate the agent logic.
    # Now it correctly calls the agent method.
    return await learning_path_agent.generate_learning_path(
        interests=interests,
        difficulty_level=difficulty_level,
        estimated_days=estimated_days
    )

async def generate_card_with_ai(
    keyword: str,
    context: Optional[str] = None,
    section_title: Optional[str] = None, # Add missing params
    course_title: Optional[str] = None,  # Add missing params
    difficulty: str = "intermediate"     # Add missing params
) -> CardCreate:
    """Legacy wrapper for backwards compatibility"""
    if not card_agent:
         raise RuntimeError("CardGeneratorAgent not initialized. Check Azure OpenAI configuration.")
    # Call the updated agent method
    return await card_agent.generate_card(
        keyword=keyword,
        context=context,
        section_title=section_title,
        course_title=course_title,
        difficulty=difficulty
        )

# --- Helper function (if needed elsewhere) ---
def get_card_generator_agent() -> CardGeneratorAgent:
     if not card_agent:
         raise RuntimeError("CardGeneratorAgent not initialized. Check Azure OpenAI configuration.")
     return card_agent

def get_learning_path_planner_agent() -> LearningPathPlannerAgent:
    if not learning_path_agent:
        raise RuntimeError("LearningPathPlannerAgent not initialized. Check Azure OpenAI configuration.")
    return learning_path_agent

async def extract_learning_goals(prompt: str) -> Tuple[List[str], str, int]:
    """Extract learning goals from a chat prompt"""
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are an expert at understanding learning goals and converting them into structured learning parameters."},
                {"role": "user", "content": f"""
                Extract learning parameters from this prompt: "{prompt}"
                Return a JSON with:
                - interests: list of relevant topics/keywords (be specific, e.g., ['Python', 'Data Analysis'])
                - difficulty_level: "beginner", "intermediate", or "advanced" (default to intermediate if unsure)
                - estimated_days: suggested number of days (between 7-90, default to 30 if unsure)
                """}
            ],
            temperature=0.5, # Slightly lower temperature for more deterministic extraction
            max_tokens=200, # Reduced tokens as the output is small
            model=deployment,
            response_format={"type": "json_object"} # Enforce JSON output if model supports it
        )

        content = response.choices[0].message.content
        # Attempt to load JSON directly
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Fallback: try extracting from markdown if direct load fails
            logging.warning(f"Failed to directly parse JSON, trying markdown extraction. Content: {content}")
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                 json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content # Assume it might be JSON without backticks
            data = json.loads(json_str)


        # Validate and provide defaults
        interests = data.get("interests", [])
        if not isinstance(interests, list) or not all(isinstance(i, str) for i in interests):
            logging.warning(f"Invalid interests format received: {interests}. Defaulting to empty list.")
            interests = []

        difficulty = data.get("difficulty_level", "intermediate").lower()
        if difficulty not in ["beginner", "intermediate", "advanced"]:
            logging.warning(f"Invalid difficulty level received: {difficulty}. Defaulting to intermediate.")
            difficulty = "intermediate"

        days = data.get("estimated_days", 30)
        if not isinstance(days, int) or not (7 <= days <= 90):
             logging.warning(f"Invalid estimated days received: {days}. Defaulting to 30.")
             days = 30

        return (interests, difficulty, days)

    except Exception as e:
        logging.error(f"Error extracting learning goals: {e}")
        logging.error(f"Original prompt: {prompt}")
        # Fallback or re-raise depending on desired behavior
        # For now, raise a specific error the endpoint can catch
        raise ValueError(f"Failed to parse learning goals from prompt: {prompt}")
    

def create_agent(agent_class, client, deployment):
    """Helper function to safely create an agent instance"""
    if client is None or deployment is None:
        logging.error(f"Cannot create {agent_class.__name__}: client={client}, deployment={deployment}")
        raise ValueError(f"Cannot create {agent_class.__name__}: Missing client or deployment")
    return agent_class(client=client, deployment=deployment)

# Then use this helper function when creating agents
try:
    agent = create_agent(CardGeneratorAgent, general_client, GENERAL_DEPLOYMENT)
except ValueError as e:
    logging.error(f"Agent creation failed: {e}")
    # Handle the error appropriately
    
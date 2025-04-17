import os
import logging
from typing import List, Dict, Any, Optional, Union, Tuple
import json
import asyncio
from openai import AzureOpenAI
from dotenv import load_dotenv
import re # Import regex

from app.learning_paths.schemas import LearningPathCreate, CourseSectionCreate
from app.courses.schemas import CourseCreate
from app.cards.schemas import CardCreate

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

class BaseAgent:
    """Base class for all AI agents"""
    
    @staticmethod
    def _extract_json_from_response(content: str) -> Dict:
        """Helper method to extract JSON from model response, with basic cleaning."""
        original_content = content # Keep original for logging if needed
        logging.debug(f"Attempting to extract JSON from: {content[:500]}...") # Log input

        try:
            # 1. Remove potential markdown wrappers first
            json_match = re.search(r'```(json)?\s*([\s\S]*?)\s*```', content, re.IGNORECASE)
            if json_match:
                content = json_match.group(2).strip()
                logging.debug("Removed markdown wrappers.")
            else:
                # If no markdown, try to find the outermost JSON object/array
                start_brace = content.find('{')
                start_bracket = content.find('[')
                end_brace = content.rfind('}')
                end_bracket = content.rfind(']')

                start = -1
                end = -1

                if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
                     # Found braces, assume it's an object
                     start = start_brace
                     end = end_brace
                elif start_bracket != -1 and end_bracket != -1 and end_bracket > start_bracket:
                     # Found brackets, assume it's an array
                     start = start_bracket
                     end = end_bracket

                if start != -1:
                     content = content[start:end+1]
                     logging.debug("Extracted content between outermost braces/brackets.")
                # else: proceed with content as is, maybe it's already clean

            # 2. Attempt direct JSON parsing
            parsed_json = json.loads(content)
            logging.debug("Successfully parsed JSON directly.")
            return parsed_json

        except json.JSONDecodeError as e:
            logging.warning(f"Initial JSON parsing failed: {e}. Content snippet: {content[:200]}...")
            # Simple cleaning attempt (e.g., for unescaped newlines) - This is basic!
            # A more robust solution might involve a dedicated JSON fixing library
            # or more sophisticated regex, but start simple.
            try:
                # Replace common issues like unescaped newlines ONLY within likely string contexts
                # This regex is still heuristic: looks for \n not preceded by \\ within quotes
                cleaned_content = re.sub(r'(?<!\\)\n', r'\\n', content)
                # Potentially add more cleaning steps here if needed (e.g., for quotes)

                if cleaned_content != content:
                     logging.warning("Attempting parsing again after cleaning newlines...")
                     parsed_json = json.loads(cleaned_content)
                     logging.debug("Successfully parsed JSON after cleaning.")
                     return parsed_json
                else:
                     # If cleaning didn't change anything, re-raise the original error
                     raise e

            except json.JSONDecodeError as e2:
                logging.error(f"JSON parsing failed even after basic cleaning: {e2}")
                logging.error(f"Original content snippet: {original_content[:500]}...")
                raise ValueError(f"Failed to parse AI response as JSON: {e2}. Original content: {original_content[:200]}...")

        except Exception as e: # Catch other potential errors during extraction
            logging.error(f"Unexpected error extracting JSON: {e}")
            logging.error(f"Original content snippet: {original_content[:500]}...")
            raise ValueError(f"Unexpected error processing AI response: {e}")

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
            # 生成缓存键
            from app.services.cache import generate_cache_key, get_or_create_cached_data
            
            cache_params = {
                "interests": sorted(interests),
                "difficulty_level": difficulty_level,
                "estimated_days": estimated_days
            }
            cache_key = generate_cache_key("learning_path", cache_params)
            
            # 使用缓存
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
                            "estimated_days": 10,
                            "sections": [
                                {{
                                    "title": "Section 1 Title",
                                    "description": "Section 1 description",
                                    "order_index": 1,
                                    "estimated_days": 3,
                                    "card_keywords": ["Keyword 1", "Keyword 2", "Keyword 3"]
                                }},
                                ...
                            ]
                        }},
                        ...
                    ]
                }}
                """
                
                response = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "You are an expert curriculum designer who creates detailed learning paths."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=3000,
                    model=deployment
                )
                
                content = response.choices[0].message.content.strip()
                data = self._extract_json_from_response(content)
                
                return data
            
            # 获取或创建缓存数据
            data, from_cache = await get_or_create_cached_data(cache_key, create_learning_path)
            if from_cache:
                logging.info(f"Retrieved learning path from cache for interests: {interests}")
            
            return data
        
        except Exception as e:
            logging.error(f"Error in learning path planner agent: {e}")
            raise

class CardGeneratorAgent(BaseAgent):
    """Agent responsible for generating detailed card content from keywords"""
    
    async def generate_card(
        self,
        keyword: str,
        context: Optional[str] = None,
        section_title: Optional[str] = None,
        course_title: Optional[str] = None
    ) -> CardCreate:
        """Generate a detailed card for a keyword with context"""
        try:
            # 生成缓存键
            from app.services.cache import generate_cache_key, get_or_create_cached_data
            
            cache_params = {
                "keyword": keyword,
                "context": context,
                "section_title": section_title,
                "course_title": course_title
            }
            cache_key = generate_cache_key("card", cache_params)
            
            # 使用缓存
            async def create_card():
                # Create a richer context for better card generation
                context_parts = []
                if context:
                    context_parts.append(f"Context: {context}")
                if section_title:
                    context_parts.append(f"Section: {section_title}")
                if course_title:
                    context_parts.append(f"Course: {course_title}")
                    
                context_str = "\n".join(context_parts) + "\n\n" if context_parts else ""
                
                prompt = f"""
                {context_str}Create a detailed explanation card for the keyword "{keyword}".
                
                The card should include:
                1. A clear explanation of the concept (3-5 paragraphs)
                2. A practical example that illustrates the concept
                3. A list of 3-5 resources for further learning (URLs with titles)
                4. Appropriate tags for categorization (at least 3 tags)
                
                Format the response as a JSON object with the following structure:
                {{
                    "keyword": "{keyword}",
                    "explanation": "Detailed explanation of the concept",
                    "example": "Practical example of the concept",
                    "resources": [
                        {{ "title": "Resource 1 Title", "url": "https://example.com/resource1" }},
                        {{ "title": "Resource 2 Title", "url": "https://example.com/resource2" }}
                    ],
                    "tags": ["tag1", "tag2", "tag3"],
                    "level": "beginner" // or "intermediate" or "advanced"
                }}
                """
                
                response = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "You are an expert educator who creates clear, comprehensive explanations."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1500,
                    model=deployment
                )
                
                content = response.choices[0].message.content.strip()
                data = self._extract_json_from_response(content)
                
                # Create card
                card = CardCreate(
                    keyword=data.get("keyword", keyword),
                    explanation=data.get("explanation", ""),
                    example=data.get("example", ""),
                    resources=data.get("resources", []),
                    tags=data.get("tags", []),
                    level=data.get("level", "beginner")
                )
                
                return card
            
            # 获取或创建缓存数据
            card, from_cache = await get_or_create_cached_data(cache_key, create_card)
            if from_cache:
                logging.info(f"Retrieved card from cache for keyword: {keyword}")
            
            return card
        
        except Exception as e:
            logging.error(f"Error in card generator agent: {e}")
            raise

class ParallelCardGeneratorManager:
    """Manager for generating multiple cards in parallel"""
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.card_generator = CardGeneratorAgent()
    
    async def generate_cards_for_section(
        self,
        keywords: List[str],
        section_title: str,
        course_title: str
    ) -> List[CardCreate]:
        """Generate multiple cards in parallel for a section"""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def _generate_with_semaphore(keyword: str) -> CardCreate:
            async with semaphore:
                return await self.card_generator.generate_card(
                    keyword=keyword,
                    section_title=section_title,
                    course_title=course_title
                )
        
        tasks = [_generate_with_semaphore(keyword) for keyword in keywords]
        return await asyncio.gather(*tasks)

# Legacy function wrappers for backward compatibility
async def generate_learning_path(
    self,
    interests: List[str],
    difficulty_level: str = "intermediate",
    estimated_days: int = 30
) -> Dict[str, Any]:
    """Generate a complete learning path with courses and sections"""
    try:
        # Generate cache key
        cache_params = {
            "interests": interests,
            "difficulty_level": difficulty_level,
            "estimated_days": estimated_days,
            "version": "1.0"  # Add a version to invalidate cache when you update the prompt
        }
        cache_key = generate_cache_key(cache_params)
        
        # Define the creator function
        async def create_learning_path():
            interests_str = ", ".join(interests)
            prompt = f"""
            Create a complete structured learning path for someone interested in {interests_str}.
            The learning path should be at {difficulty_level} level and designed to be completed in approximately {estimated_days} days.
            
            # ... rest of your prompt ...
            """
            
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are an expert curriculum designer who creates detailed learning paths."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=3000,
                model=deployment
            )
            
            content = response.choices[0].message.content.strip()
            return self._extract_json_from_response(content)
        
        # Get from cache or create
        data, is_cached = await get_or_create_cached_data(cache_key, create_learning_path)
        
        if is_cached:
            logging.info(f"Retrieved learning path from cache for interests: {interests}")
        else:
            logging.info(f"Generated new learning path for interests: {interests}")
        
        return data
        
    except Exception as e:
        logging.error(f"Error in learning path planner agent: {e}")
        raise
    
async def generate_card_with_ai(
    keyword: str,
    context: Optional[str] = None
) -> CardCreate:
    """Legacy wrapper for backwards compatibility"""
    generator = CardGeneratorAgent()
    return await generator.generate_card(keyword=keyword, context=context)

async def generate_learning_path_with_ai(
    interests: List[str],
    difficulty_level: str = "intermediate",
    estimated_days: int = 30
) -> Dict[str, Any]:
    """Legacy wrapper function for backward compatibility"""
    agent = LearningPathPlannerAgent()
    return await agent.generate_learning_path(
        interests=interests,
        difficulty_level=difficulty_level,
        estimated_days=estimated_days
    )

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
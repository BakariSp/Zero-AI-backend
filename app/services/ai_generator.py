import os
import logging
from typing import List, Dict, Any, Optional, Union
import json
import asyncio
from openai import AzureOpenAI
from dotenv import load_dotenv

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
        """Helper method to extract JSON from model response"""
        try:
            # Extract JSON if it's wrapped in markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            return json.loads(content)
        except Exception as e:
            logging.error(f"Error extracting JSON from response: {e}")
            logging.error(f"Original content: {content}")
            raise ValueError("Failed to parse AI response as JSON")

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
import logging
import json
import re
import asyncio
from typing import Dict, Any, Optional, List, Union
from openai import AzureOpenAI # Assuming sync client, use AsyncOpenAI if preferred
from pydantic import BaseModel, Field

# Import sub-agents (adjust paths if they differ)
from .path_planner import PathPlannerAgent
from .course_generator import CourseGeneratorAgent
from .section_generator import SectionGeneratorAgent
from .card_generator import CardGeneratorAgent

class DialogueInput(BaseModel):
    user_input: str = Field(..., description="The user's latest text input.")
    chat_history: List[str] = Field([], description="Previous turns in the conversation.")
    current_plan: Optional[Dict[str, Any]] = Field(None, description="The existing learning plan structure, if any.")

# You could also define a detailed response model, but for now
# we'll rely on the structure returned by the agent.
# class DialogueResponse(BaseModel):
#     ai_reply: str
#     result: Dict[str, Any]
#     status: Dict[str, bool]
#     triggered_agent: str 

# --- Shared JSON Extraction Utility ---
# (Consider moving this to a common utils module)
def _extract_json_from_response(content: str) -> Any:
    """Safely extracts JSON object or list from AI response content."""
    logging.debug(f"Attempting to extract JSON from: {content[:500]}...") # Log start of content
    try:
        # First, try loading directly, assuming perfect JSON
        return json.loads(content)
    except json.JSONDecodeError:
        # If direct load fails, look for markdown code blocks
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            logging.debug(f"Found JSON within markdown block: {extracted[:500]}...")
            try:
                return json.loads(extracted)
            except json.JSONDecodeError as e_inner:
                logging.warning(f"Failed to parse JSON from markdown block: {e_inner}")
                # Fall through to find first '{' or '['
        else:
             logging.debug("No markdown block found.")

        # If no code block, find the first '{' or '[' and last '}' or ']'
        start_obj = content.find('{')
        start_arr = content.find('[')
        start = -1

        if start_obj != -1 and start_arr != -1:
            start = min(start_obj, start_arr)
        elif start_obj != -1:
            start = start_obj
        elif start_arr != -1:
            start = start_arr

        if start != -1:
            end_obj = content.rfind('}')
            end_arr = content.rfind(']')
            end = max(end_obj, end_arr)

            if end > start:
                potential_json = content[start:end+1]
                logging.debug(f"Trying JSON substring from first/last bracket: {potential_json[:500]}...")
                try:
                    return json.loads(potential_json)
                except json.JSONDecodeError as e_sub:
                    logging.error(f"Failed to parse JSON substring: {e_sub}")

    logging.error(f"Could not extract valid JSON from response content after all attempts.")
    raise ValueError("AI response did not contain valid JSON.")
# --- End Shared Utility ---


class DialoguePlannerAgent:    
    def __init__(self, client: Union[AzureOpenAI, Any], deployment: str):        
        """        
        Initializes the DialoguePlannerAgent and its sub-agents.        
        Args:            
        client: An initialized client instance (AzureOpenAI or ZhipuAIClient).            
        deployment: The deployment/model name for the LLM to use for planning/reply generation.                        
        Sub-agents might use the same or different deployments based on their init.        
        """        
        self.client = client        
        self.deployment = deployment        
        logging.info(f"Initializing DialoguePlannerAgent with deployment '{deployment}'...")        
        # Initialize sub-agents - Pass the client and potentially specific deployments if needed        
        # # For simplicity, using the same client/deployment for all now.        
        try:            
            # # Assuming sub-agents also take client and deployment            
            self.path_planner = PathPlannerAgent(client, deployment)            
            self.course_generator = CourseGeneratorAgent(client, deployment)            
            self.section_generator = SectionGeneratorAgent(client, deployment)            
            self.card_generator = CardGeneratorAgent(client, deployment)            
            logging.info("All sub-agents initialized successfully.")        
        except Exception as e:            
            logging.error(f"Failed to initialize one or more sub-agents: {e}", exc_info=True)            
            # Depending on requirements, you might want to raise the error            
            # or allow the planner to work with potentially missing agents.            
            raise RuntimeError("DialoguePlanner failed to initialize sub-agents.") from e

    async def _determine_intent_and_entities(self, user_input: str, current_plan: Optional[dict], chat_history: List[str]) -> Dict[str, Any]:
        """Uses LLM to determine intent and extract relevant entities."""
        # Simple Rule: If no plan exists, the primary intent is likely to create one.
        if not current_plan:
            logging.info("No current_plan found, defaulting intent to CREATE_PATH.")
            # Basic entity extraction (can be improved with LLM later if needed for this case)
            entities = {"interests": [user_input], "difficulty_level": "intermediate", "estimated_days": 30}
            return {"intent": "CREATE_PATH", "entities": entities}

        # Use LLM for intent recognition when a plan exists or input is complex
        history_str = "\n".join(f" - {msg}" for msg in chat_history)
        # Summarize plan to avoid excessive token usage
        plan_summary = "Plan exists but details omitted for brevity." if current_plan else "None"
        if current_plan:
             plan_structure = {
                 "path_title": current_plan.get("learning_path", {}).get("title"),
                 "course_titles": [c.get("title") for c in current_plan.get("courses", []) if c.get("title")],
                 # Add section titles if needed, but keep it concise
             }
             plan_summary = f"Current plan structure: {json.dumps(plan_structure)}"


        prompt = f"""
Analyze the user's request based on the latest input, chat history, and the current learning plan state.

Chat History (if any):
{history_str if history_str else "N/A"}

{plan_summary}

Latest User Input: "{user_input}"

Determine the primary intent from these options:
- CREATE_PATH: User wants to start a new learning path from scratch (usually when no plan exists or explicitly requested).
- ADD_COURSE_OUTLINE: User wants suggestions for new courses/topics to add to the existing path.
- GENERATE_COURSE_DETAILS: User wants to flesh out specific course titles (provided or implied) into detailed sections.
- ADD_SECTION: User wants to add more sections to a specific existing course.
- GENERATE_CARDS: User wants to generate flashcards for a specific topic, section, or keywords.
- GENERAL_CHAT: User is asking a question or making a comment not directly related to generating content.
- AMBIGUOUS: The intent is unclear or requires clarification.

Extract key entities mentioned by the user relevant to the intent. Examples:
- For CREATE_PATH: interests (list of strings), difficulty_level (string), estimated_days (int).
- For ADD_COURSE_OUTLINE: interests/topic (list or string), difficulty_level, estimated_days.
- For GENERATE_COURSE_DETAILS: titles (list of course titles), difficulty_level, estimated_days.
- For ADD_SECTION: topic (string, the course title to add sections to), num_sections (int), existing_sections (list of titles).
- For GENERATE_CARDS: topic (string, e.g., section title), keywords (list of strings), num_cards (int), difficulty_level, course_title (string).

Respond ONLY with a single JSON object containing "intent" (string) and "entities" (object).
Example 1: {{"intent": "GENERATE_CARDS", "entities": {{"topic": "Python Decorators", "num_cards": 5, "difficulty_level": "intermediate"}}}}
Example 2: {{"intent": "ADD_COURSE_OUTLINE", "entities": {{"interests": ["Advanced Python", "Asyncio"]}}}}
Example 3: {{"intent": "CREATE_PATH", "entities": {{"interests": ["Game Development in Godot"], "difficulty_level": "beginner"}}}}
"""
        logging.debug(f"Determining intent with prompt:\n{prompt}")
        try:
            # Use asyncio.to_thread for synchronous client in async function
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.deployment,
                messages=[
                    {"role": "system", "content": "You are an intent recognition expert for a learning path generator bot. Respond only in JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1, # Low temp for deterministic intent classification
                max_tokens=400,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content.strip()
            intent_data = _extract_json_from_response(content) # Use robust extraction
            if not isinstance(intent_data, dict) or "intent" not in intent_data or "entities" not in intent_data:
                 logging.error(f"LLM intent response malformed: {intent_data}")
                 raise ValueError("Intent response missing required keys.")
            logging.info(f"Determined intent: {intent_data.get('intent')}, Entities: {intent_data.get('entities')}")
            return intent_data
        except Exception as e:
            logging.error(f"Error determining intent via LLM: {e}", exc_info=True)
            return {"intent": "AMBIGUOUS", "entities": {}} # Fallback

    async def _generate_ai_reply(self, user_input: str, action_taken: str, result_summary: str, triggered_agent: str) -> str:
        """Generates a conversational AI reply using LLM."""
        prompt = f"""
You are a friendly and helpful AI assistant guiding a user in creating a learning plan.
The user's latest input was: "{user_input}"

Based on their request, the system performed the following action (triggered agent: {triggered_agent}): {action_taken}.

Summary of the result/content generated: {result_summary}

Craft a brief, helpful, and conversational reply to the user (1-3 sentences).
- Acknowledge their request.
- Briefly mention what was generated or done.
- If content was generated, hint at what they could ask for next (e.g., "Let me know if you'd like details for a course", "Shall I generate flashcards for this section?").
- If the intent was ambiguous or general chat, provide a helpful holding response or answer briefly.
"""
        logging.debug(f"Generating AI reply with prompt:\n{prompt}")
        try:
             response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.deployment,
                messages=[
                    {"role": "system", "content": "You are a friendly AI learning assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=150
            )
             reply = response.choices[0].message.content.strip()
             # Basic cleanup - only remove quotes at the beginning and end if they wrap the entire message
             if reply.startswith('"') and reply.endswith('"') and reply.count('"') == 2:
                 reply = reply[1:-1]
             return reply
        except Exception as e:
            logging.error(f"Error generating AI reply: {e}", exc_info=True)
            return "I've processed your request. What would you like to do next?" # Fallback reply

    async def process_user_input(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes user input, determines intent, orchestrates sub-agents,
        and returns the structured response.

        Args:
            user_input: The user's latest text input.
            context: A dictionary potentially containing:
                - current_plan (Optional[dict]): The existing learning plan structure.
                - chat_history (List[str]): Previous turns in the conversation.

        Returns:
            A dictionary matching the specified API output structure.
        """
        logging.info(f"DialoguePlanner processing user input: '{user_input}'")
        current_plan = context.get("current_plan")
        chat_history = context.get("chat_history", [])

        # 1. Determine Intent & Entities
        intent_data = await self._determine_intent_and_entities(user_input, current_plan, chat_history)
        intent = intent_data.get("intent", "AMBIGUOUS")
        entities = intent_data.get("entities", {})

        # Initialize response structure based on the required output format
        response = {
            "ai_reply": "Okay, let me see what I can do...", # Placeholder
            "result": {
                "learning_path": None,
                "courses": None,
                "sections": None,
                "cards": None
            },
            "status": { # Initial status based on incoming plan
                "has_learning_path": bool(current_plan and current_plan.get("learning_path")),
                "has_courses": bool(current_plan and current_plan.get("courses")),
                "has_sections": bool(current_plan and any(s for c in current_plan.get("courses", []) for s in c.get("sections", []))),
                "has_cards": False # Card status is hard to track globally here
            },
            "triggered_agent": "None"
        }

        agent_result = None
        action_description = "analyzing the request" # Default description

        # 2. Prepare context & Call appropriate agent based on intent
        try:
            # Standardize context for sub-agents where possible
            agent_context = entities.copy() # Start with extracted entities
            agent_context.setdefault("difficulty_level", "intermediate")
            agent_context.setdefault("estimated_days", 30)

            if intent == "CREATE_PATH":
                response["triggered_agent"] = "PathPlanner"
                action_description = f"generating a new learning path for interests: {agent_context.get('interests')}"
                logging.info(f"Action: {action_description}")
                # PathPlanner expects: interests, difficulty_level, estimated_days
                path_context = {
                    "interests": agent_context.get("interests", ["general topic"]),
                    "difficulty_level": agent_context["difficulty_level"],
                    "estimated_days": agent_context.get("estimated_days", 30)
                }
                agent_result = await self.path_planner.generate_path(path_context)
                # PathPlanner returns the full structure
                if agent_result:
                    response["result"]["learning_path"] = agent_result.get("learning_path")
                    response["result"]["courses"] = agent_result.get("courses")
                    # Update status based on generation
                    response["status"]["has_learning_path"] = bool(response["result"]["learning_path"])
                    response["status"]["has_courses"] = bool(response["result"]["courses"])
                    response["status"]["has_sections"] = bool(response["result"]["courses"]) # Assume sections included

            elif intent == "ADD_COURSE_OUTLINE":
                response["triggered_agent"] = "CourseGenerator (Outline)"
                action_description = f"suggesting new course titles based on: {agent_context.get('interests') or agent_context.get('topic')}"
                logging.info(f"Action: {action_description}")
                # CourseGenerator.generate_course_outline expects: interests, difficulty, days, existing_items, limit
                outline_context = {
                    "interests": agent_context.get("interests", agent_context.get("topic", ["general topic"])),
                    "difficulty_level": agent_context["difficulty_level"],
                    "estimated_days": agent_context.get("estimated_days", 30),
                    "existing_items": [c["title"] for c in current_plan.get("courses", []) if c.get("title")] if current_plan else [],
                    "limit": agent_context.get("limit", 5)
                }
                agent_result = await self.course_generator.generate_course_outline(outline_context)
                # Result is {"titles": [...]}. Adapt to response structure.
                if agent_result and agent_result.get("titles"):
                    # Represent titles as minimal course objects for the result structure
                    response["result"]["courses"] = [{"title": title, "description": None, "sections": []} for title in agent_result["titles"]]
                    # Status flags aren't strongly affected by just titles
                    response["status"]["has_courses"] = True # Indicate courses (titles) are available

            elif intent == "GENERATE_COURSE_DETAILS":
                response["triggered_agent"] = "CourseGenerator (Details)"
                titles_to_detail = agent_context.get("titles", agent_context.get("topic"))
                if not titles_to_detail:
                    raise ValueError("Missing 'titles' or 'topic' entity for GENERATE_COURSE_DETAILS")
                if isinstance(titles_to_detail, str): titles_to_detail = [titles_to_detail] # Ensure list
                action_description = f"generating detailed sections for course(s): {', '.join(titles_to_detail)}"
                logging.info(f"Action: {action_description}")
                # CourseGenerator.generate_course expects: titles, difficulty, days
                details_context = {
                    "titles": titles_to_detail,
                    "difficulty_level": agent_context["difficulty_level"],
                    "estimated_days": agent_context.get("estimated_days", len(titles_to_detail) * 7) # Adjust days estimate
                }
                agent_result = await self.course_generator.generate_course(details_context)
                if agent_result and agent_result.get("courses"):
                    response["result"]["courses"] = agent_result["courses"]
                    response["status"]["has_courses"] = True
                    response["status"]["has_sections"] = True # Details include sections

            elif intent == "ADD_SECTION":
                response["triggered_agent"] = "SectionGenerator"
                target_topic = agent_context.get("topic")
                if not target_topic:
                    raise ValueError("Missing 'topic' (course title) entity for ADD_SECTION")
                action_description = f"generating new sections for course: '{target_topic}'"
                logging.info(f"Action: {action_description}")
                # SectionGenerator.generate_section expects: topic, course_context, num_sections, difficulty, existing_sections
                # Find existing sections for the target course from current_plan
                existing_section_titles = []
                if current_plan and current_plan.get("courses"):
                    for course in current_plan["courses"]:
                        if course.get("title") == target_topic:
                            existing_section_titles = [s.get("title") for s in course.get("sections", []) if s.get("title")]
                            break
                section_context = {
                    "topic": target_topic,
                    "course_context": agent_context.get("course_context", f"Course: {target_topic}"), # Provide some context
                    "num_sections": agent_context.get("num_sections", 3),
                    "difficulty_level": agent_context["difficulty_level"],
                    "existing_sections": existing_section_titles
                }
                agent_result = await self.section_generator.generate_section(section_context)
                if agent_result and agent_result.get("sections"):
                    response["result"]["sections"] = agent_result["sections"]
                    response["status"]["has_sections"] = True

            elif intent == "GENERATE_CARDS":
                response["triggered_agent"] = "CardGenerator"
                subject = agent_context.get("topic") or ", ".join(agent_context.get("keywords", []))
                if not subject:
                     raise ValueError("Missing 'topic' or 'keywords' entity for GENERATE_CARDS")
                num_cards = agent_context.get("num_cards", 5)
                action_description = f"generating {num_cards} flashcard(s) for: '{subject}'"
                logging.info(f"Action: {action_description}")
                # CardGenerator.generate_card expects: context dict with topic/keywords, num_cards, etc.
                card_context = {
                    "topic": agent_context.get("topic"),
                    "keywords": agent_context.get("keywords"),
                    "num_cards": num_cards,
                    "difficulty_level": agent_context["difficulty_level"],
                    "course_title": agent_context.get("course_title"), # May need lookup from plan
                    "broader_context": agent_context.get("broader_context")
                }
                # TODO: Find course_title from current_plan if topic is a section title?
                agent_result = await self.card_generator.generate_card(card_context) # generate_card generates multiple
                if agent_result and agent_result.get("cards"):
                    response["result"]["cards"] = agent_result["cards"]
                    response["status"]["has_cards"] = True

            elif intent == "GENERAL_CHAT" or intent == "AMBIGUOUS":
                response["triggered_agent"] = "DialoguePlanner (Chat)"
                action_description = "responding to the general query or ambiguity"
                logging.info(f"Action: {action_description}")
                # No sub-agent call needed, reply generated later
                agent_result = {} # No structured result

            else:
                 # Should not happen if intent enum is exhaustive
                 logging.warning(f"Unhandled intent type: {intent}")
                 response["triggered_agent"] = "DialoguePlanner (Error)"
                 action_description = "trying to understand the request"
                 agent_result = {}

        except Exception as e:
            logging.error(f"Error during agent orchestration for intent '{intent}': {e}", exc_info=True)
            response["ai_reply"] = f"Sorry, I encountered an error while trying to {action_description}. Please try again or rephrase your request. Error: {e}"
            # Reset results and status on error
            response["result"] = {"learning_path": None, "courses": None, "sections": None, "cards": None}
            response["status"] = {"has_learning_path": False, "has_courses": False, "has_sections": False, "has_cards": False}
            response["triggered_agent"] = "Error"
            return response # Return early

        # 3. Generate Final AI Reply based on action and result summary
        result_summary = "No specific content was generated this turn."
        if agent_result:
            parts = []
            if response["result"]["learning_path"]: parts.append("a learning path structure")
            # Handle course titles vs full courses
            if intent == "ADD_COURSE_OUTLINE" and response["result"]["courses"]:
                 parts.append(f"{len(response['result']['courses'])} course title suggestions")
            elif response["result"]["courses"]:
                 parts.append(f"{len(response['result']['courses'])} course(s) with details")

            if response["result"]["sections"]: parts.append(f"{len(response['result']['sections'])} section(s)")
            if response["result"]["cards"]: parts.append(f"{len(response['result']['cards'])} card(s)")

            if parts:
                result_summary = f"Generated {', '.join(parts)}."
            elif intent == "GENERAL_CHAT" or intent == "AMBIGUOUS":
                 result_summary = "I provided a direct response or asked for clarification."


        response["ai_reply"] = await self._generate_ai_reply(
            user_input,
            action_description,
            result_summary,
            response["triggered_agent"]
        )

        # Final status update - reflects the state *after* this turn's generation.
        # If a path was generated, it implies courses/sections were too (based on PathPlanner).
        # If course details were generated, it implies sections were too.
        # This reflects the content available in the *current* response["result"].
        response["status"]["has_learning_path"] = bool(response["result"]["learning_path"])
        response["status"]["has_courses"] = bool(response["result"]["courses"])
        response["status"]["has_sections"] = bool(response["result"]["sections"] or \
                                                 (response["result"]["courses"] and any(c.get("sections") for c in response["result"]["courses"])))
        response["status"]["has_cards"] = bool(response["result"]["cards"])


        logging.info(f"DialoguePlanner final response status: {response['status']}")
        # logging.debug(f"DialoguePlanner final response data: {response}") # Can be very verbose
        return response

# Note: The instantiation and use of DialoguePlannerAgent would typically happen
# in an API route handler (like FastAPI). That handler would be responsible for
# obtaining the AzureOpenAI client (e.g., via dependency injection) and
# managing the 'current_plan' and 'chat_history' state between requests.

# Example (Conceptual) FastAPI Route Usage:
#
# from fastapi import FastAPI, Depends, Body
# from app.services.agents.dialogue_planner import DialoguePlannerAgent
# # Assume get_openai_client provides the AzureOpenAI client instance
# from app.dependencies import get_openai_client, get_deployment_name
#
# app = FastAPI()
#
# @app.post("/api/ai/dialogue")
# async def handle_dialogue_endpoint(
#     user_input: str = Body(..., embed=True),
#     chat_history: List[str] = Body([], embed=True),
#     current_plan: Optional[dict] = Body(None, embed=True),
#     client: AzureOpenAI = Depends(get_openai_client),
#     deployment: str = Depends(get_deployment_name) # Get appropriate deployment
# ):
#     planner = DialoguePlannerAgent(client=client, deployment=deployment)
#     context = {
#         "current_plan": current_plan,
#         "chat_history": chat_history
#     }
#     response = await planner.process_user_input(user_input, context)
#     # The API route might then update the session state with the new results
#     # before returning the response to the client.
#     return response 


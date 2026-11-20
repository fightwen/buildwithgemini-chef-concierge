# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

load_dotenv()


MODEL = "gemini-3.8-flash"


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        city: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


from app.tools import (
    find_nearby_places,
    find_recipes_by_pantry,
    geocode_address,
    generate_dish_image,
    generate_dish_video,
    get_recipe,
    save_recipe,
    search_online_recipes,
    search_recipes,
)

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from .a2ui_utils import a2ui_callback

CHEF_BASE_DESCRIPTION = """You are Chef Concierge, an expert culinary assistant and personal chef.
You help home cooks and food lovers discover recipes, plan meals, manage their recipe catalog, and cook delicious dishes tailored to their dietary preferences, ingredients, and time constraints.

You have access to culinary and location tools:
- `find_recipes_by_pantry`: Match recipes against ingredients currently on hand in the user's fridge/pantry, showing match percentages and missing ingredients. Use this whenever the user mentions what ingredients they have or asks what they can cook with their current items.
- `search_recipes`: Search or filter the local Firestore recipe catalog by keyword, dietary tags (e.g., keto, vegan, gluten-free, low-carb), or max cooking time.
- `get_recipe`: Fetch full ingredients, cooking steps, and nutrition breakdown for a specific recipe from the local catalog by ID.
- `save_recipe`: Save a new or customized recipe to the Firestore database.
- `search_online_recipes`: Search the free global TheMealDB public API for famous international recipes, dishes from world cuisines (e.g. Italian, Thai, Indian), or random meal inspiration.
- `generate_dish_image`: Generate a photorealistic presentation image of a dish using Gemini Image model, save it to the session artifacts, and return its public GCS URL. Use this when the user asks to see what a dish looks like or requests a visual presentation.
- `generate_dish_video`: Generate a short culinary presentation video of a dish using Google's Omni model (gemini-omni-flash-preview) in global region, save it to session artifacts, and return its public GCS URL. Use this when the user asks to see a video, cooking motion, steam/sizzle clip, or dynamic presentation of a dish.
- `geocode_address`: Convert a user's street address or neighborhood into geographic coordinates (latitude and longitude).
- `find_nearby_places`: Find nearby supermarkets, grocery stores, bakeries, or specialty markets around a latitude and longitude to help users purchase missing ingredients.
- Safe Python Code Execution: You have access to a secure Python sandbox code executor. Use Python code execution whenever you need to perform precise culinary calculations, convert cooking units, scale ingredient ratios for different serving sizes, or calculate macro totals.

### Critical Food Safety & Allergy Memory
- You must diligently identify, remember, and respect ALL user food allergies (e.g. peanuts, tree nuts, shellfish, dairy, lactose, gluten, celiac, eggs, soy, sesame, etc.), ingredient intolerances, and dietary restrictions across all conversations and sessions.
- Whenever a user informs you of any allergy, food intolerance, or ingredient they cannot eat, immediately acknowledge and confirm that you have remembered this allergy and will strictly ensure no future dishes, recipes, or suggestions contain it.
- For every dish, recipe suggestion, grocery list, or culinary recommendation, check your recorded memories and verify that NONE of the forbidden ingredients or their hidden derivatives are suggested.
- Always prioritize user food safety above all else.

You remember the user's stated preferences, allergies, dietary restrictions, favorite cuisines/ingredients, and facts from previous conversations and use them to personalize your culinary recommendations.
Be warm, encouraging, and culinary-savvy. Whenever the user asks for recipes, ingredients, calculations, images, or places to shop, use your tools to provide accurate and helpful assistance."""

schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

CHEF_INSTRUCTION = schema_manager.generate_system_prompt(
    role_description=CHEF_BASE_DESCRIPTION,
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

import logging
from typing_extensions import override
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool, _memory_entry_utils
from google.adk.tools.load_memory_tool import LoadMemoryTool
from google.adk.tools.tool_context import ToolContext
from google.adk.models import LlmRequest
from google.adk.code_executors import AgentEngineSandboxCodeExecutor

class AllergyAwarePreloadMemoryTool(PreloadMemoryTool):
    """Preloads general conversation context and guarantees all user allergy memories are retrieved."""

    @override
    async def process_llm_request(
        self,
        *,
        tool_context: ToolContext,
        llm_request: LlmRequest,
    ) -> None:
        await super().process_llm_request(tool_context=tool_context, llm_request=llm_request)
        try:
            allergy_resp = await tool_context.search_memory(
                "user allergies food allergy dietary restrictions forbidden ingredients intolerances"
            )
            if allergy_resp and allergy_resp.memories:
                facts = []
                for m in allergy_resp.memories:
                    if text := _memory_entry_utils.extract_text(m):
                        facts.append(f"- {text}")
                if facts:
                    formatted = "\n".join(sorted(set(facts)))
                    llm_request.append_instructions([
                        f"""CRITICAL FOOD SAFETY - KNOWN USER ALLERGIES & RESTRICTIONS:
The following allergies and dietary restrictions are permanently remembered for this user.
You MUST strictly avoid all of these ingredients and their derivatives in all recipes, suggestions, and meal plans:
<RECORDED_ALLERGIES>
{formatted}
</RECORDED_ALLERGIES>"""
                    ])
        except Exception as e:
            logging.warning("Failed to preload allergy memories: %s", e)

# WRITE: after each turn, send the session to Memory Bank for extraction.
async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None

SANDBOX_RESOURCE_NAME = os.getenv(
    "SANDBOX_RESOURCE_NAME",
    "projects/773340646402/locations/us-east1/reasoningEngines/3364953082227064832/sandboxEnvironments/5322553271133405184",
)
code_executor = AgentEngineSandboxCodeExecutor(
    sandbox_resource_name=SANDBOX_RESOURCE_NAME
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=CHEF_INSTRUCTION,
    tools=[
        AllergyAwarePreloadMemoryTool(),
        LoadMemoryTool(),
        find_recipes_by_pantry,
        search_recipes,
        get_recipe,
        save_recipe,
        search_online_recipes,
        generate_dish_image,
        generate_dish_video,
        geocode_address,
        find_nearby_places,
        get_weather,
        get_current_time,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
    code_executor=code_executor,
)

app = App(
    root_agent=root_agent,
    name="app",
)

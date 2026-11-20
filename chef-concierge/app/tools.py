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

"""Firestore-backed culinary tools for chef-concierge."""

import base64
import json
import os
import re
import time
import urllib.parse
import urllib.request
from typing import Any
from dotenv import load_dotenv
from google import genai
from google.adk.tools import ToolContext
from google.cloud import firestore, storage
from google.genai import types

load_dotenv()

# Hardcoded project ID and public bucket name as strings to avoid project number issues on Agent Platform
PROJECT_ID = "qwiklabs-gcp-03-005c40b02edd"
BUCKET_NAME = "chef-concierge-dishes-qwiklabs-gcp-03-005c40b02edd"

_db: firestore.Client | None = None
_genai_client: genai.Client | None = None
_storage_client: storage.Client | None = None


def _get_db() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client(project=PROJECT_ID)
    return _db


def _get_genai_client() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
    return _genai_client


def _get_storage_client() -> storage.Client:
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client(project=PROJECT_ID)
    return _storage_client


def search_recipes(
    keyword: str = "",
    dietary_tag: str = "",
    max_cook_time_minutes: int = 0,
) -> str:
    """Searches and filters recipes in the Firestore recipe catalog.

    Use this tool when the user asks for meal ideas, wants to browse recipes,
    or is looking for dishes matching specific diets (e.g. keto, vegan, gluten-free)
    or time constraints.

    Args:
        keyword: Optional search keyword to match recipe title, cuisine, or ingredients (e.g., 'salmon', 'tofu', 'Italian').
        dietary_tag: Optional dietary tag filter (e.g., 'keto', 'vegan', 'vegetarian', 'gluten-free', 'low-carb').
        max_cook_time_minutes: Optional maximum cooking time in minutes (0 means no limit).

    Returns:
        A list of matching recipe summaries with ID, title, cuisine, cook time, and tags.
    """
    try:
        db = _get_db()
        docs = db.collection("recipes").stream()
        results = []

        kw = keyword.lower().strip()
        tag = dietary_tag.lower().strip()

        for doc in docs:
            data = doc.to_dict() or {}
            title = data.get("title", "")
            description = data.get("description", "")
            cuisine = data.get("cuisine", "")
            cook_time = data.get("cook_time_minutes", 0)
            tags = [t.lower() for t in data.get("dietary_tags", [])]
            ingredients = [i.lower() for i in data.get("ingredients", [])]

            if tag and tag not in tags:
                continue

            if max_cook_time_minutes > 0 and cook_time > max_cook_time_minutes:
                continue

            if kw:
                text_to_search = f"{title} {description} {cuisine} {' '.join(ingredients)}".lower()
                if kw not in text_to_search:
                    continue

            results.append({
                "id": doc.id,
                "title": title,
                "cuisine": cuisine,
                "difficulty": data.get("difficulty", "Medium"),
                "cook_time_minutes": cook_time,
                "dietary_tags": data.get("dietary_tags", []),
                "calories": data.get("nutrition", {}).get("calories", "N/A"),
            })

        if not results:
            return f"No recipes found matching criteria (keyword='{keyword}', tag='{dietary_tag}', max_time={max_cook_time_minutes}m)."

        lines = [f"Found {len(results)} recipe(s):"]
        for r in results:
            tags_str = ", ".join(r["dietary_tags"])
            lines.append(
                f"- [{r['id']}] {r['title']} ({r['cuisine']}, {r['difficulty']}, {r['cook_time_minutes']} min, {r['calories']} kcal) [Tags: {tags_str}]"
            )
        lines.append("\nTip: Use get_recipe(recipe_id) to see full ingredients and step-by-step instructions.")
        return "\n".join(lines)
    except Exception as e:
        return f"Error searching recipes in Firestore: {str(e)}"


def get_recipe(recipe_id: str) -> str:
    """Retrieves full details, ingredients, and instructions for a specific recipe.

    Args:
        recipe_id: The unique ID of the recipe (e.g. 'garlic-butter-salmon', 'crispy-airfryer-tofu').

    Returns:
        Full recipe details including description, ingredients list, cooking steps, and nutrition info.
    """
    try:
        db = _get_db()
        doc = db.collection("recipes").document(recipe_id.strip()).get()
        if not doc.exists:
            return f"Recipe '{recipe_id}' not found in the catalog."

        data = doc.to_dict() or {}
        lines = [
            f"=== {data.get('title', recipe_id)} ===",
            f"ID: {doc.id}",
            f"Cuisine: {data.get('cuisine', 'N/A')}",
            f"Difficulty: {data.get('difficulty', 'N/A')}",
            f"Prep Time: {data.get('prep_time_minutes', 0)} mins | Cook Time: {data.get('cook_time_minutes', 0)} mins",
            f"Servings: {data.get('servings', 1)}",
            f"Dietary Tags: {', '.join(data.get('dietary_tags', []))}",
            f"\nDescription:\n{data.get('description', '')}",
            "\nIngredients:"
        ]
        for ing in data.get("ingredients", []):
            lines.append(f"  • {ing}")

        lines.append("\nInstructions:")
        for idx, step in enumerate(data.get("instructions", []), 1):
            lines.append(f"  {idx}. {step}")

        nutrition = data.get("nutrition", {})
        if nutrition:
            lines.append(
                f"\nNutrition per serving: {nutrition.get('calories', 'N/A')} kcal | "
                f"Protein: {nutrition.get('protein_g', 'N/A')}g | "
                f"Carbs: {nutrition.get('carbs_g', 'N/A')}g | "
                f"Fat: {nutrition.get('fat_g', 'N/A')}g"
            )

        if "notes" in data and data["notes"]:
            lines.append(f"\nChef's Notes: {data['notes']}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving recipe '{recipe_id}': {str(e)}"


def save_recipe(
    title: str,
    description: str,
    cuisine: str,
    difficulty: str,
    prep_time_minutes: int,
    cook_time_minutes: int,
    servings: int,
    ingredients: list[str],
    instructions: list[str],
    dietary_tags: list[str],
    calories: int = 0,
    protein_g: int = 0,
    carbs_g: int = 0,
    fat_g: int = 0,
) -> str:
    """Saves a new recipe or custom dish to the Firestore recipe catalog.

    Args:
        title: Title of the dish (e.g. 'Lemon Herb Grilled Chicken').
        description: A short appetizing description of the dish.
        cuisine: Cuisine style (e.g. 'Mediterranean', 'Mexican', 'Asian').
        difficulty: Cooking difficulty ('Easy', 'Medium', or 'Hard').
        prep_time_minutes: Preparation time in minutes.
        cook_time_minutes: Active cooking time in minutes.
        servings: Number of servings this recipe yields.
        ingredients: List of ingredients with measurements.
        instructions: Ordered list of step-by-step cooking instructions.
        dietary_tags: List of dietary categories (e.g. ['keto', 'high-protein']).
        calories: Calories per serving (optional, default 0).
        protein_g: Grams of protein per serving (optional, default 0).
        carbs_g: Grams of carbohydrates per serving (optional, default 0).
        fat_g: Grams of fat per serving (optional, default 0).

    Returns:
        Confirmation message with the new recipe ID.
    """
    try:
        db = _get_db()
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
        if not slug:
            slug = "custom-recipe"

        recipe_data = {
            "id": slug,
            "title": title,
            "description": description,
            "cuisine": cuisine,
            "difficulty": difficulty,
            "prep_time_minutes": prep_time_minutes,
            "cook_time_minutes": cook_time_minutes,
            "servings": servings,
            "ingredients": ingredients,
            "instructions": instructions,
            "dietary_tags": dietary_tags,
            "nutrition": {
                "calories": calories,
                "protein_g": protein_g,
                "carbs_g": carbs_g,
                "fat_g": fat_g,
            },
        }

        db.collection("recipes").document(slug).set(recipe_data)
        return f"Successfully saved recipe '{title}' to Firestore with ID '{slug}'."
    except Exception as e:
        return f"Error saving recipe '{title}': {str(e)}"


def find_recipes_by_pantry(available_ingredients: list[str]) -> str:
    """Matches recipes against ingredients currently on hand in the user's pantry or fridge.

    Use this tool when the user tells you what ingredients they have and asks what
    dishes they can make or what ingredients they are missing.

    Args:
        available_ingredients: List of ingredient names currently on hand (e.g. ['salmon', 'butter', 'garlic'] or ['tofu', 'soy sauce']).

    Returns:
        A list of matching recipes ranked by match percentage, showing which ingredients are matched and which are missing.
    """
    try:
        db = _get_db()
        docs = db.collection("recipes").stream()

        on_hand = [ing.lower().strip() for ing in available_ingredients if ing.strip()]
        if not on_hand:
            return "Please provide at least one ingredient you have on hand."

        matches = []
        for doc in docs:
            data = doc.to_dict() or {}
            recipe_ingredients = data.get("ingredients", [])
            if not recipe_ingredients:
                continue

            matched = []
            missing = []

            for r_ing in recipe_ingredients:
                r_lower = r_ing.lower()
                if any(item in r_lower for item in on_hand):
                    matched.append(r_ing)
                else:
                    missing.append(r_ing)

            match_count = len(matched)
            if match_count > 0:
                match_pct = int((match_count / len(recipe_ingredients)) * 100)
                matches.append({
                    "id": doc.id,
                    "title": data.get("title", doc.id),
                    "cuisine": data.get("cuisine", "N/A"),
                    "cook_time": data.get("cook_time_minutes", 0),
                    "match_pct": match_pct,
                    "matched_count": match_count,
                    "total_count": len(recipe_ingredients),
                    "missing": missing,
                })

        if not matches:
            return f"No recipes in the catalog use any of your available ingredients: {', '.join(on_hand)}."

        matches.sort(key=lambda x: x["match_pct"], reverse=True)

        lines = [f"Found {len(matches)} recipe(s) matching your ingredients ({', '.join(on_hand)}):\n"]
        for m in matches:
            status = "READY TO COOK! (100% Match)" if m["match_pct"] == 100 else f"{m['match_pct']}% match ({m['matched_count']}/{m['total_count']} ingredients)"
            lines.append(f"• [{m['id']}] {m['title']} ({m['cuisine']}, {m['cook_time']} min) — {status}")
            if m["missing"]:
                lines.append(f"  Missing: {', '.join(m['missing'])}")

        lines.append("\nTip: Use get_recipe(recipe_id) to see full cooking instructions.")
        return "\n".join(lines)
    except Exception as e:
        return f"Error matching recipes: {str(e)}"


def search_online_recipes(query: str = "") -> str:
    """Fetches real live recipes from the free global TheMealDB public API.

    Use this tool when the user wants global culinary inspiration beyond the local catalog,
    asks for famous dishes from world cuisines (e.g. Italian, Thai, Indian), or wants
    a random meal idea.

    Args:
        query: Search term for a dish or main ingredient (e.g. 'curry', 'pasta', 'arrabiata', or 'random').

    Returns:
        Real recipe details from TheMealDB with dish name, cuisine area, category, image URL, and instructions.
    """
    api_key = os.getenv("THEMEALDB_API_KEY", "1")
    q = query.strip()
    if not q or q.lower() == "random":
        url = f"https://www.themealdb.com/api/json/v1/{api_key}/random.php"
    else:
        encoded_q = urllib.parse.quote(q)
        url = f"https://www.themealdb.com/api/json/v1/{api_key}/search.php?s={encoded_q}"

    req = urllib.request.Request(url, headers={"User-Agent": "ChefConcierge/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        meals = data.get("meals")
        if not meals:
            return f"No global recipes found on TheMealDB for '{query}'."

        results = []
        for meal in meals[:3]:
            ingredients = []
            for i in range(1, 21):
                ing = meal.get(f"strIngredient{i}")
                meas = meal.get(f"strMeasure{i}")
                if ing and ing.strip():
                    measure_str = f" ({meas.strip()})" if meas and meas.strip() else ""
                    ingredients.append(f"{ing.strip()}{measure_str}")

            instructions = (meal.get("strInstructions") or "").replace("\r\n", " ").strip()
            if len(instructions) > 350:
                instructions = instructions[:350] + "..."

            results.append(
                f"=== {meal.get('strMeal')} ===\n"
                f"Cuisine: {meal.get('strArea', 'Unknown')} | Category: {meal.get('strCategory', 'General')}\n"
                f"Photo URL: {meal.get('strMealThumb', 'N/A')}\n"
                f"Key Ingredients: {', '.join(ingredients[:8])}\n"
                f"Instructions: {instructions}"
            )
        return "\n\n".join(results)
    except Exception as e:
        return f"Error querying TheMealDB API: {str(e)}"


def geocode_address(address: str) -> str:
    """Converts a street address or location name into geographic coordinates (latitude and longitude).

    Use this tool to find coordinates when the user provides an address and wants
    to find nearby supermarkets, grocery stores, or specialty markets.

    Args:
        address: The street address, city, or neighborhood to geocode (e.g. '1600 Amphitheatre Pkwy, Mountain View, CA').

    Returns:
        Formatted address and latitude/longitude coordinates.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

    try:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(address.strip())}&key={api_key}"
        req = urllib.request.Request(url, headers={"User-Agent": "ChefConcierge/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if data.get("status") != "OK" or not data.get("results"):
            return f"Geocoding failed for '{address}': status {data.get('status')} - {data.get('error_message', 'No results')}"

        result = data["results"][0]
        formatted_address = result.get("formatted_address")
        location = result.get("geometry", {}).get("location", {})
        lat = location.get("lat")
        lng = location.get("lng")

        return f"Address: {formatted_address}\nLocation: ({lat}, {lng})\nLatitude: {lat}\nLongitude: {lng}"
    except Exception as e:
        return f"Error during geocoding: {str(e)}"


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "supermarket",
    radius_meters: float = 5000.0,
) -> str:
    """Searches for nearby places of a specific type around a location using the Google Places API (New).

    Use this tool to find nearby grocery stores, supermarkets, bakeries, or markets
    where the user can purchase ingredients.

    Args:
        latitude: Latitude of the center point (e.g. 37.422).
        longitude: Longitude of the center point (e.g. -122.084).
        place_type: Type of place to search for (e.g. 'supermarket', 'grocery_store', 'bakery', 'restaurant'). Defaults to 'supermarket'.
        radius_meters: Search radius in meters (max 50000.0). Defaults to 5000.0 (5 km).

    Returns:
        A list of nearby places with name, formatted address, and location coordinates.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

    try:
        url = "https://places.googleapis.com/v1/places:searchNearby"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
        }
        payload = {
            "includedTypes": [place_type.strip()],
            "maxResultCount": 5,
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": float(latitude),
                        "longitude": float(longitude),
                    },
                    "radius": float(radius_meters),
                }
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        places = data.get("places", [])
        if not places:
            return f"No nearby '{place_type}' places found within {int(radius_meters)}m of ({latitude}, {longitude})."

        lines = [f"Found {len(places)} nearby '{place_type}' place(s):"]
        for p in places:
            name = p.get("displayName", {}).get("text", "Unknown Name")
            address = p.get("formattedAddress", "Unknown Address")
            loc = p.get("location", {})
            p_lat = loc.get("latitude")
            p_lng = loc.get("longitude")
            lines.append(f"- Name: {name}\n  Address: {address}\n  Location: ({p_lat}, {p_lng})")

        return "\n\n".join(lines)
    except Exception as e:
        return f"Error during nearby places search: {str(e)}"


async def generate_dish_image(
    dish_name: str,
    description: str = "",
    tool_context: ToolContext | None = None,
) -> str:
    """Generates a photorealistic dish presentation image using the gemini-3.1-flash-lite-image model in global region.

    Saves the image as an artifact in the session so it appears in the Playground's Artifacts panel,
    and uploads the image bytes directly to the project's public Cloud Storage bucket without writing to local disk.

    Args:
        dish_name: Name of the dish to visualize (e.g. 'Pan-Seared Garlic Butter Salmon' or 'Creamy Truffle Wild Mushroom Risotto').
        description: Optional details about plating, ingredients, or garnish.

    Returns:
        A confirmation message with the artifact filename and the public HTTPS URL for the uploaded image.
    """
    try:
        client = _get_genai_client()
        detail = f", {description}" if description else ""
        prompt = (
            f"Professional food photography of {dish_name}{detail}. "
            "Beautifully plated on high-end ceramic dishware, restaurant presentation, "
            "natural soft lighting, vibrant fresh garnish, shallow depth of field, high resolution, 4k."
        )

        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
        )

        image_bytes = None
        mime_type = "image/jpeg"
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type
                    break

        if not image_bytes:
            return f"Unable to generate image for '{dish_name}'. No image bytes returned by model."

        slug = re.sub(r"[^a-zA-Z0-9]+", "-", dish_name.lower()).strip("-")
        if not slug:
            slug = "dish"
        ext = "jpg" if "jpeg" in mime_type else "png"
        filename = f"{slug}_{int(time.time())}.{ext}"

        # 1. Save with tool_context.save_artifact so it shows in Playground's Artifacts panel
        if tool_context:
            artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload image bytes to public Cloud Storage bucket in memory (no local file)
        storage_client = _get_storage_client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
        return (
            f"Successfully generated visual presentation for '{dish_name}'!\n"
            f"Artifact saved: {filename}\n"
            f"Public Image URL: {public_url}"
        )
    except Exception as e:
        return f"Error generating dish image: {str(e)}"


async def generate_dish_video(
    dish_name: str,
    description: str = "",
    tool_context: ToolContext | None = None,
) -> str:
    """Generates a short culinary presentation video for a dish using Google's Omni model (gemini-omni-flash-preview) in the global region.

    Saves the video as an artifact in the session so it appears in the Playground's Artifacts panel,
    and uploads the video bytes directly to the project's public Cloud Storage bucket without writing to local disk.

    Args:
        dish_name: Name of the dish or culinary item to visualize (e.g. 'Sizzling Garlic Butter Shrimp' or 'Molten Chocolate Lava Cake').
        description: Optional details about motion, sizzle, steam, or plating presentation.

    Returns:
        A confirmation message with the artifact filename and the public HTTPS URL for the uploaded video.
    """
    try:
        client = _get_genai_client()
        detail = f", {description}" if description else ""
        prompt = (
            f"Cinematic close-up food video of {dish_name}{detail}. "
            "Sizzling, steam gently rising, beautiful gourmet plating, 4k food commercial, appetizing motion."
        )

        interaction = client.interactions.create(
            model="gemini-omni-flash-preview",
            store=False,
            input=[{"type": "text", "text": prompt}],
            response_format=[{
                "type": "video",
                "delivery": "inline",
                "aspect_ratio": "16:9",
                "duration": "5s",
            }],
        )

        video_bytes = None
        mime_type = "video/mp4"

        if interaction and getattr(interaction, "steps", None):
            for step in interaction.steps:
                contents = getattr(step, "content", None) or getattr(step, "contents", None) or []
                for item in contents:
                    item_data = getattr(item, "data", None)
                    item_mime = getattr(item, "mime_type", None)
                    if item_data:
                        if isinstance(item_data, str):
                            try:
                                video_bytes = base64.b64decode(item_data)
                            except Exception:
                                video_bytes = item_data.encode("utf-8")
                        elif isinstance(item_data, bytes):
                            video_bytes = item_data
                        if item_mime:
                            mime_type = item_mime
                        break
                if video_bytes:
                    break

        if not video_bytes:
            return f"Unable to generate video for '{dish_name}'. No video bytes returned by model."

        slug = re.sub(r"[^a-zA-Z0-9]+", "-", dish_name.lower()).strip("-")
        if not slug:
            slug = "dish_video"
        filename = f"{slug}_{int(time.time())}.mp4"

        # 1. Save with tool_context.save_artifact so it shows in Playground's Artifacts panel
        if tool_context:
            artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
            await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload video bytes to public Cloud Storage bucket in memory (no local file)
        storage_client = _get_storage_client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
        return (
            f"Successfully generated culinary presentation video for '{dish_name}'!\n"
            f"Artifact saved: {filename}\n"
            f"Public Video URL: {public_url}"
        )
    except Exception as e:
        return f"Error generating dish video: {str(e)}"






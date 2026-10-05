# ruff: noqa
# Copyright 2026 Google LLC

import base64
import json
import os
import urllib.parse
import urllib.request
import uuid
from typing import List, Optional
from dotenv import load_dotenv
from google import genai
from google.cloud import firestore, storage

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory.vertex_ai_memory_bank_service import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from .a2ui_utils import a2ui_callback

load_dotenv()

PROJECT_ID = "qwiklabs-gcp-02-8fe52a72cc9e"
COLLECTION_NAME = "apartment_listings"
BUCKET_NAME = "urbannest-media-qwiklabs-gcp-02-8fe52a72cc9e"
MEMORY_BANK_ID = "3438728113427578880"

# Initialize clients with hardcoded Project ID
db = firestore.Client(project=PROJECT_ID)
storage_client = storage.Client(project=PROJECT_ID)

# Load Agent Engine resource name from deployment_metadata.json for sandbox code execution
DEPLOYMENT_METADATA_PATH = os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")
agent_engine_resource_name = None
if os.path.exists(DEPLOYMENT_METADATA_PATH):
    try:
        with open(DEPLOYMENT_METADATA_PATH, "r") as f:
            metadata = json.load(f)
            agent_engine_resource_name = metadata.get("remote_agent_runtime_id")
    except Exception:
        pass

code_executor = (
    AgentEngineSandboxCodeExecutor(agent_engine_resource_name=agent_engine_resource_name)
    if agent_engine_resource_name
    else None
)


async def generate_memories_callback(callback_context: CallbackContext):
    """Callback to extract and save long-term memories to Memory Bank after each agent turn."""
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        print(f"Memory callback notice: {e}")
    return None


def memory_service_builder():
    """Builds Vertex AI Memory Bank service instance for deployed environment."""
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location="us-east1",
        agent_engine_id=MEMORY_BANK_ID,
    )


def search_apartment_listings(
    neighborhood: Optional[str] = None,
    max_price: Optional[int] = None,
    min_bedrooms: Optional[int] = None,
    pets_allowed: Optional[bool] = None,
) -> str:
    """Searches apartment listings in Firestore based on filter criteria.

    Args:
        neighborhood: Optional neighborhood name (e.g. 'SoMa', 'Mission District', 'Richmond', 'Marina').
        max_price: Optional maximum monthly rent budget in USD.
        min_bedrooms: Optional minimum number of bedrooms.
        pets_allowed: Optional boolean flag if pet-friendly housing is required.

    Returns:
        A list of matching apartment listings with their details.
    """
    try:
        query_ref = db.collection(COLLECTION_NAME)
        docs = query_ref.stream()

        results = []
        for doc in docs:
            data = doc.to_dict()

            if neighborhood and neighborhood.lower() not in data.get("neighborhood", "").lower():
                continue
            if max_price and data.get("price", 0) > max_price:
                continue
            if min_bedrooms is not None and data.get("bedrooms", 0) < min_bedrooms:
                continue
            if pets_allowed and not data.get("pets_allowed", False):
                continue

            results.append(data)

        if not results:
            return "No apartment listings found matching your criteria."

        output = f"Found {len(results)} matching apartment listing(s):\n"
        for item in results:
            output += (
                f"- [{item.get('id')}] {item.get('title')}: ${item.get('price')}/mo, "
                f"{item.get('bedrooms')} Bed / {item.get('bathrooms')} Bath, "
                f"Neighborhood: {item.get('neighborhood')}, Pets Allowed: {'Yes' if item.get('pets_allowed') else 'No'}\n"
                f"  Amenities: {', '.join(item.get('amenities', []))}\n"
            )
        return output
    except Exception as e:
        return f"Error searching apartment listings: {str(e)}"


def get_apartment_details(listing_id: str) -> str:
    """Retrieves full details for a specific apartment listing by its ID.

    Args:
        listing_id: The unique ID of the apartment listing (e.g. 'apt_101').

    Returns:
        Detailed information for the specified apartment listing.
    """
    try:
        doc_ref = db.collection(COLLECTION_NAME).document(listing_id)
        doc = doc_ref.get()
        if not doc.exists:
            return f"Listing with ID '{listing_id}' was not found."

        data = doc.to_dict()
        return (
            f"Apartment Details for {data.get('title')} (ID: {listing_id}):\n"
            f"- Neighborhood: {data.get('neighborhood')}, {data.get('city')}\n"
            f"- Price: ${data.get('price')}/month\n"
            f"- Layout: {data.get('bedrooms')} Bed / {data.get('bathrooms')} Bath ({data.get('sqft')} sqft)\n"
            f"- Pet Policy: {'Pet friendly' if data.get('pets_allowed') else 'No pets'}\n"
            f"- Available Date: {data.get('available_date')}\n"
            f"- Amenities: {', '.join(data.get('amenities', []))}\n"
            f"- Description: {data.get('description')}\n"
        )
    except Exception as e:
        return f"Error retrieving apartment details: {str(e)}"


def add_apartment_listing(
    title: str,
    neighborhood: str,
    price: int,
    bedrooms: int,
    bathrooms: float,
    sqft: int,
    pets_allowed: bool,
    amenities: List[str],
    description: str,
    available_date: str,
    city: str = "San Francisco",
    custom_id: Optional[str] = None,
) -> str:
    """Adds or updates an apartment listing in the Firestore database.

    Args:
        title: Descriptive title for the apartment.
        neighborhood: Neighborhood name (e.g. 'SoMa', 'Pacific Heights').
        price: Monthly rent in USD.
        bedrooms: Number of bedrooms.
        bathrooms: Number of bathrooms.
        sqft: Square footage.
        pets_allowed: True if pets are permitted.
        amenities: List of amenity tags (e.g. ['parking', 'balcony']).
        description: Full description text.
        available_date: Available date string (e.g. '2026-11-01').
        city: City name (defaults to 'San Francisco').
        custom_id: Optional custom listing ID (e.g. 'apt_105').

    Returns:
        Confirmation message with the listing ID.
    """
    try:
        if custom_id:
            listing_id = custom_id
        else:
            doc_ref = db.collection(COLLECTION_NAME).document()
            listing_id = f"apt_{doc_ref.id[:6]}"

        listing_data = {
            "id": listing_id,
            "title": title,
            "neighborhood": neighborhood,
            "city": city,
            "price": price,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "sqft": sqft,
            "pets_allowed": pets_allowed,
            "amenities": amenities,
            "description": description,
            "available_date": available_date,
        }

        db.collection(COLLECTION_NAME).document(listing_id).set(listing_data)
        return f"Successfully added apartment listing '{title}' with ID '{listing_id}' to Firestore!"
    except Exception as e:
        return f"Error adding apartment listing: {str(e)}"


def generate_room_concept(
    style_description: str,
    listing_id: Optional[str] = None,
    room_type: str = "living room",
) -> str:
    """Generates a virtual interior design concept image rendering for an apartment room using AI.

    Args:
        style_description: The interior design aesthetic (e.g. 'boho-chic', 'mid-century modern', 'minimalist industrial').
        listing_id: Optional listing ID to link the concept rendering to (e.g. 'apt_101').
        room_type: Room type to visualize (e.g. 'living room', 'bedroom', 'kitchen', 'balcony').

    Returns:
        A formatted string with the public image URL of the generated virtual staging concept rendering.
    """
    try:
        genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location="us-central1")

        prompt = (
            f"A professional 3D interior design rendering of a {room_type} in an apartment, "
            f"staged in a {style_description} style, brightly lit with natural sunlight."
        )

        response = genai_client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt,
        )

        image_bytes = None
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                image_bytes = part.inline_data.data
                break

        if not image_bytes:
            return "Failed to generate virtual staging image concept."

        filename = f"staging_concepts/{listing_id or 'general'}_{uuid.uuid4().hex[:8]}.png"
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type="image/png")

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"

        listing_info = f" for Listing {listing_id}" if listing_id else ""
        return (
            f"Successfully generated virtual staging concept{listing_info}!\n"
            f"- Room Type: {room_type.title()}\n"
            f"- Style: {style_description}\n"
            f"- Concept Image URL: {public_url}\n"
            f"You can view or embed this image directly."
        )
    except Exception as e:
        return f"Error generating room concept image: {str(e)}"


async def generate_floor_plan(
    tool_context: ToolContext,
    description: str = "Modern 2-bedroom luxury apartment layout with open kitchen, balcony, and hardwood floors",
    listing_id: Optional[str] = None,
) -> str:
    """Generates an architectural 2D floor plan rendering image for an apartment using gemini-3.1-flash-lite-image in the global region.

    Saves the generated image as an artifact in the Playground Artifacts panel and uploads it directly
    to public Cloud Storage without writing to a local file.

    Args:
        tool_context: ADK ToolContext instance for saving session artifacts.
        description: Description of the apartment floor plan layout.
        listing_id: Optional listing ID associated with the floor plan layout (e.g. 'apt_101').

    Returns:
        The public HTTPS URL of the uploaded Cloud Storage object.
    """
    try:
        genai_client = genai.Client(vertexai=True, project="qwiklabs-gcp-02-8fe52a72cc9e", location="global")

        prompt = (
            f"Generate a clear, high-quality 2D architectural floor plan blueprint rendering for an apartment: {description}"
        )

        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
        )

        image_bytes = None
        mime_type = "image/png"
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                image_bytes = part.inline_data.data
                if part.inline_data.mime_type:
                    mime_type = part.inline_data.mime_type
                break

        if not image_bytes:
            return "Failed to generate floor plan image."

        # 1. Save with tool_context.save_artifact for Playground Artifacts panel
        artifact_filename = f"floor_plan_{listing_id or 'concept'}_{uuid.uuid4().hex[:8]}.png"
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=artifact_filename, artifact=artifact_part)

        # 2. Upload same image bytes directly to public GCS bucket (hardcoded string)
        bucket_name = "urbannest-media-qwiklabs-gcp-02-8fe52a72cc9e"
        object_key = f"floor_plans/{artifact_filename}"
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(object_key)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{bucket_name}/{object_key}"
        return (
            f"Successfully generated floor plan image!\n"
            f"- Saved to Playground Artifacts as: {artifact_filename}\n"
            f"- Public Cloud Storage URL: {public_url}"
        )
    except Exception as e:
        return f"Error generating floor plan image: {str(e)}"


async def generate_apartment_tour_video(
    tool_context: ToolContext,
    description: str = "Cinematic video tour walking through a sunny luxury apartment living room with hardwood floors and city balcony views",
    listing_id: Optional[str] = None,
) -> str:
    """Generates a short virtual video tour for an apartment listing using Google's Omni model (gemini-omni-flash-preview) in the global region.

    Saves the generated video as an artifact in the Playground Artifacts panel and uploads it directly
    to public Cloud Storage without writing to a local file.

    Args:
        tool_context: ADK ToolContext instance for saving session artifacts.
        description: Description or prompt for the apartment video tour walkthrough.
        listing_id: Optional listing ID associated with the apartment (e.g. 'apt_101').

    Returns:
        The public HTTPS URL of the uploaded Cloud Storage object.
    """
    try:
        genai_client = genai.Client(vertexai=True, project="qwiklabs-gcp-02-8fe52a72cc9e", location="global")

        prompt = f"A 5-second cinematic video tour walking through an apartment: {description}"

        interaction = genai_client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt,
        )

        video_bytes = None
        if hasattr(interaction, "output_video") and interaction.output_video:
            data = getattr(interaction.output_video, "data", None)
            if data:
                if isinstance(data, str):
                    video_bytes = base64.b64decode(data)
                elif isinstance(data, bytes):
                    video_bytes = data

        if not video_bytes:
            return "Failed to generate apartment video tour."

        mime_type = "video/mp4"

        # 1. Save with tool_context.save_artifact for Playground Artifacts panel
        artifact_filename = f"video_tour_{listing_id or 'concept'}_{uuid.uuid4().hex[:8]}.mp4"
        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=artifact_filename, artifact=artifact_part)

        # 2. Upload same video bytes directly to public GCS bucket (hardcoded string)
        bucket_name = "urbannest-media-qwiklabs-gcp-02-8fe52a72cc9e"
        object_key = f"video_tours/{artifact_filename}"
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(object_key)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{bucket_name}/{object_key}"
        return (
            f"Successfully generated apartment video tour!\n"
            f"- Saved to Playground Artifacts as: {artifact_filename}\n"
            f"- Public Cloud Storage URL: {public_url}"
        )
    except Exception as e:
        return f"Error generating apartment video tour: {str(e)}"



def calculate_affordability(
    monthly_income: float,
    rent: float,
    security_deposit_months: float = 1.0,
    estimated_utilities: float = 150.0,
) -> str:
    """Calculates apartment rent affordability ratio and total upfront move-in cash required.

    Args:
        monthly_income: Gross monthly income in USD.
        rent: Monthly rent price in USD.
        security_deposit_months: Security deposit expressed in months of rent (default 1.0).
        estimated_utilities: Estimated monthly utility cost in USD (default 150.0).

    Returns:
        Summary of rent-to-income percentage, total monthly housing cost, and upfront move-in cash needed.
    """
    if monthly_income <= 0:
        return "Monthly income must be greater than zero."

    total_monthly = rent + estimated_utilities
    rent_ratio = (rent / monthly_income) * 100
    total_housing_ratio = (total_monthly / monthly_income) * 100

    upfront_deposit = rent * security_deposit_months
    upfront_total = rent + upfront_deposit

    is_affordable = total_housing_ratio <= 33.0
    status = "Affordable" if is_affordable else "Above recommended 33% budget threshold"

    return (
        f"Affordability & Move-In Summary:\n"
        f"- Rent-to-Income Ratio: {rent_ratio:.1f}% (Total Housing Ratio: {total_housing_ratio:.1f}%)\n"
        f"- Assessment: {status}\n"
        f"- Total Monthly Housing Cost: ${total_monthly:,.2f} (Rent: ${rent:,.2f} + Utilities: ${estimated_utilities:,.2f})\n"
        f"- Upfront Move-In Cost: ${upfront_total:,.2f} (First Month: ${rent:,.2f} + Deposit: ${upfront_deposit:,.2f})\n"
    )


def lookup_zip_code_location(zip_code: str) -> str:
    """Looks up city, state, and geographic coordinates for a 5-digit US ZIP code using Zippopotam.us public API.

    Args:
        zip_code: 5-digit US ZIP code (e.g. '94103', '94110').

    Returns:
        Formatted summary with city, state, latitude, and longitude for the requested ZIP code.
    """
    clean_zip = zip_code.strip()
    if not clean_zip.isdigit() or len(clean_zip) != 5:
        return f"Invalid ZIP code '{zip_code}'. Please provide a 5-digit US ZIP code."

    base_url = os.getenv("ZIP_LOOKUP_API_URL", "https://api.zippopotam.us/us")
    url = f"{base_url}/{clean_zip}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "UrbanNestFinder/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status != 200:
                return f"Could not retrieve location details for ZIP code '{clean_zip}'."
            data = json.loads(response.read().decode("utf-8"))

        places = data.get("places", [])
        if not places:
            return f"No location records found for ZIP code '{clean_zip}'."

        place = places[0]
        return (
            f"Location Info for ZIP Code {clean_zip}:\n"
            f"- City: {place.get('place name')}\n"
            f"- State: {place.get('state')} ({place.get('state abbreviation')})\n"
            f"- Coordinates: Latitude {place.get('latitude')}, Longitude {place.get('longitude')}\n"
            f"- Country: {data.get('country')}"
        )
    except Exception as e:
        return f"Error looking up location for ZIP code '{clean_zip}': {str(e)}"


def geocode_address(address: str) -> str:
    """Converts a street address into geographic coordinates (latitude and longitude) using the Google Maps Geocoding API.

    Args:
        address: The address string to geocode (e.g. '742 Mission St, San Francisco, CA').

    Returns:
        Formatted summary with key fields: formatted address, latitude, and longitude.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key or api_key == "PASTE_KEY_HERE":
        return "Google Maps API key is not configured. Please set GOOGLE_MAPS_API_KEY in your local .env file."

    encoded_address = urllib.parse.quote(address)
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))

        if data.get("status") != "OK":
            return f"Geocoding failed for address '{address}': {data.get('status')} - {data.get('error_message', 'No details')}"

        results = data.get("results", [])
        if not results:
            return f"No geocoding results found for address '{address}'."

        first_result = results[0]
        formatted_address = first_result.get("formatted_address")
        location = first_result.get("geometry", {}).get("location", {})
        lat = location.get("lat")
        lng = location.get("lng")

        return (
            f"Geocoding Result for '{address}':\n"
            f"- Address: {formatted_address}\n"
            f"- Location: Latitude {lat}, Longitude {lng}"
        )
    except Exception as e:
        return f"Error calling Geocoding API: {str(e)}"


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "restaurant",
    radius_meters: float = 1000.0,
) -> str:
    """Finds nearby places (e.g., restaurants, cafes, parks, transit stations) around coordinates using Google Places API (New).

    Args:
        latitude: Latitude coordinate.
        longitude: Longitude coordinate.
        place_type: Place type to search for (e.g. 'restaurant', 'cafe', 'park', 'transit_station', 'supermarket').
        radius_meters: Search radius in meters (default 1000.0 meters).

    Returns:
        Formatted summary of nearby places with key fields (name, address, location coordinates).
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key or api_key == "PASTE_KEY_HERE":
        return "Google Maps API key is not configured. Please set GOOGLE_MAPS_API_KEY in your local .env file."

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
    }
    payload = {
        "includedTypes": [place_type],
        "maxResultCount": 10,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": radius_meters,
            }
        },
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))

        places = data.get("places", [])
        if not places:
            return f"No nearby '{place_type}' places found within {radius_meters}m of ({latitude}, {longitude})."

        output = f"Found {len(places)} nearby '{place_type}' place(s):\n"
        for place in places:
            display_name = place.get("displayName", {}).get("text", "Unknown Name")
            address = place.get("formattedAddress", "N/A")
            loc = place.get("location", {})
            lat = loc.get("latitude")
            lng = loc.get("longitude")
            output += f"- Name: {display_name}\n  Address: {address}\n  Location: ({lat}, {lng})\n"

        return output
    except Exception as e:
        return f"Error calling Places API (New): {str(e)}"


a2ui_schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = a2ui_schema_manager.generate_system_prompt(
    role_description=(
        "You are UrbanNest Apartment Finder, an intelligent real estate assistant. "
        "You help users search, filter, and view apartment listings from the database, "
        "look up location coordinates by address or ZIP code, discover nearby amenities and places, "
        "calculate rent affordability and move-in costs, generate floor plan architectural blueprints, "
        "generate short virtual video tours using Google's Omni model (gemini-omni-flash-preview), "
        "execute Python code calculations safely in a sandbox, "
        "remember user preferences and facts across conversations using Memory Bank, "
        "and generate custom AI virtual staging room concept renderings."
    ),
    workflow_description="Analyze the request, call appropriate tools, and return structured UI when appropriate.",
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
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects.\n\n"
        "MEMORY & ALLERGIES INSTRUCTIONS:\n"
        "- Pay close attention to any user allergies or health preferences (such as pet allergies, "
        "food/dietary allergies, or environmental allergies) mentioned in conversation.\n"
        "- Remember all user allergies across sessions using Memory Bank.\n"
        "- Ensure that future apartment recommendations, amenity filters, and nearby place searches "
        "strictly respect and account for all remembered user allergies."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=code_executor,
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
    instruction=a2ui_instruction,
    tools=[
        PreloadMemoryTool(),
        search_apartment_listings,
        get_apartment_details,
        add_apartment_listing,
        generate_room_concept,
        generate_floor_plan,
        generate_apartment_tour_video,
        calculate_affordability,
        lookup_zip_code_location,
        geocode_address,
        find_nearby_places,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)

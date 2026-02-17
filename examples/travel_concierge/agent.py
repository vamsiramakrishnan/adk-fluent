"""
Travel Concierge: Multi-agent travel advisory system.

Converted from adk-samples travel-concierge -- root coordinator with 6
specialist sub-agent groups (inspiration, planning, booking, pre-trip,
in-trip, post-trip) covering the full travel lifecycle.

Original: https://github.com/google/adk-samples/tree/main/python/agents/travel-concierge

Usage:
    cd examples
    adk web travel_concierge
"""

import json
import os
from datetime import datetime
from typing import Any

from adk_fluent import Agent
from dotenv import load_dotenv
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.sessions.state import State
from google.adk.tools import ToolContext, google_search
from google.adk.tools.agent_tool import AgentTool
from google.genai.types import GenerateContentConfig
from pydantic import BaseModel, Field

from .prompt import (
    BOOKING_AGENT_PROMPT,
    CONFIRM_RESERVATION_PROMPT,
    FLIGHT_SEARCH_PROMPT,
    FLIGHT_SEAT_SELECTION_PROMPT,
    HOTEL_ROOM_SELECTION_PROMPT,
    HOTEL_SEARCH_PROMPT,
    INSPIRATION_AGENT_PROMPT,
    INTRIP_AGENT_PROMPT,
    ITINERARY_AGENT_PROMPT,
    LOGISTIC_PROMPT_TEMPLATE,
    NEED_ITINERARY_PROMPT,
    PAYMENT_CHOICE_PROMPT,
    PLACE_AGENT_PROMPT,
    PLANNING_AGENT_PROMPT,
    POI_AGENT_PROMPT,
    POSTTRIP_AGENT_PROMPT,
    PRETRIP_AGENT_PROMPT,
    PROCESS_PAYMENT_PROMPT,
    ROOT_AGENT_PROMPT,
    SEARCH_GROUNDING_PROMPT,
    TRIP_MONITOR_PROMPT,
    WHATTOPACK_PROMPT,
)

load_dotenv()

MODEL = "gemini-2.5-flash"

# ---------------------------------------------------------------------------
# State constants (keys into ADK session state)
# ---------------------------------------------------------------------------

SYSTEM_TIME = "_time"
ITIN_INITIALIZED = "_itin_initialized"
ITIN_KEY = "itinerary"
PROF_KEY = "user_profile"
ITIN_START_DATE = "itinerary_start_date"
ITIN_END_DATE = "itinerary_end_date"
ITIN_DATETIME = "itinerary_datetime"
START_DATE = "start_date"
END_DATE = "end_date"

# ---------------------------------------------------------------------------
# Pydantic output schemas (consolidated from shared_libraries/types.py)
# ---------------------------------------------------------------------------

json_response_config = GenerateContentConfig(
    response_mime_type="application/json"
)


class Destination(BaseModel):
    name: str = Field(description="A Destination's Name")
    country: str = Field(description="The Destination's Country Name")
    image: str = Field(description="verified URL to an image of the destination")
    highlights: str = Field(description="Short description highlighting key features")
    rating: str = Field(description="Numerical rating (e.g., 4.5)")


class DestinationIdeas(BaseModel):
    places: list[Destination]


class POI(BaseModel):
    place_name: str = Field(description="Name of the attraction")
    address: str = Field(description="An address or sufficient info to geocode")
    lat: str = Field(description="Latitude (e.g., 20.6843)")
    long: str = Field(description="Longitude (e.g., -88.5678)")
    review_ratings: str = Field(description="Rating (e.g. 4.8)")
    highlights: str = Field(description="Short description highlighting key features")
    image_url: str = Field(description="verified URL to an image")
    map_url: str | None = Field(description="Verified URL to Google Map")
    place_id: str | None = Field(description="Google Map place_id")


class POISuggestions(BaseModel):
    places: list[POI]


class AirportEvent(BaseModel):
    city_name: str
    airport_code: str
    timestamp: str


class Flight(BaseModel):
    flight_number: str
    departure: AirportEvent
    arrival: AirportEvent
    airlines: list[str]
    airline_logo: str
    price_in_usd: int
    number_of_stops: int


class FlightsSelection(BaseModel):
    flights: list[Flight]


class Seat(BaseModel):
    is_available: bool
    price_in_usd: int
    seat_number: str


class SeatsSelection(BaseModel):
    seats: list[list[Seat]]


class Hotel(BaseModel):
    name: str
    address: str
    check_in_time: str
    check_out_time: str
    thumbnail: str
    price: int


class HotelsSelection(BaseModel):
    hotels: list[Hotel]


class Room(BaseModel):
    is_available: bool
    price_in_usd: int
    room_type: str


class RoomsSelection(BaseModel):
    rooms: list[Room]


class AttractionEvent(BaseModel):
    event_type: str = Field(default="visit")
    description: str
    address: str
    start_time: str
    end_time: str
    booking_required: bool = Field(default=False)
    price: str | None = None


class FlightEvent(BaseModel):
    event_type: str = Field(default="flight")
    description: str
    booking_required: bool = Field(default=True)
    departure_airport: str
    arrival_airport: str
    flight_number: str
    boarding_time: str
    seat_number: str
    departure_time: str
    arrival_time: str
    price: str | None = None
    booking_id: str | None = None


class HotelEvent(BaseModel):
    event_type: str = Field(default="hotel")
    description: str
    address: str
    check_in_time: str
    check_out_time: str
    room_selection: str
    booking_required: bool = Field(default=True)
    price: str | None = None
    booking_id: str | None = None


class ItineraryDay(BaseModel):
    day_number: int
    date: str
    events: list[FlightEvent | HotelEvent | AttractionEvent] = Field(default=[])


class Itinerary(BaseModel):
    trip_name: str
    start_date: str
    end_date: str
    origin: str
    destination: str = ""
    days: list[ItineraryDay] = Field(default_factory=list)


class PackingList(BaseModel):
    items: list[str]


# ---------------------------------------------------------------------------
# Tools  (consolidated from tools/ directory)
# ---------------------------------------------------------------------------

SAMPLE_SCENARIO_PATH = os.getenv(
    "TRAVEL_CONCIERGE_SCENARIO",
    "travel_concierge/profiles/itinerary_empty_default.json",
)


def memorize(key: str, value: str, tool_context: ToolContext):
    """Memorize pieces of information, one key-value pair at a time."""
    tool_context.state[key] = value
    return {"status": f'Stored "{key}": "{value}"'}


def map_tool(key: str, tool_context: ToolContext):
    """Inspect POIs stored under `key` in state and verify lat/lon via Places API."""
    if key not in tool_context.state:
        tool_context.state[key] = {}
    if "places" not in tool_context.state[key]:
        tool_context.state[key]["places"] = []

    pois = tool_context.state[key]["places"]

    # Attempt Places API lookup if key is available
    places_api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if places_api_key:
        import requests

        for poi in pois:
            location = poi["place_name"] + ", " + poi["address"]
            url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
            params = {
                "input": location,
                "inputtype": "textquery",
                "fields": "place_id,formatted_address,name,geometry",
                "key": places_api_key,
            }
            try:
                resp = requests.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                if data.get("candidates"):
                    c = data["candidates"][0]
                    poi["place_id"] = c.get("place_id")
                    poi["map_url"] = (
                        f"https://www.google.com/maps/place/?q=place_id:{c['place_id']}"
                        if c.get("place_id")
                        else None
                    )
                    loc = c.get("geometry", {}).get("location", {})
                    if loc:
                        poi["lat"] = str(loc["lat"])
                        poi["long"] = str(loc["lng"])
            except Exception:
                pass

    return {"places": pois}


# --- In-trip monitoring tools ---


def flight_status_check(
    flight_number: str, flight_date: str, checkin_time: str, departure_time: str
):
    """Checks the status of a flight, given its flight_number, date, checkin_time and departure_time."""
    return {"status": f"Flight {flight_number} checked"}


def event_booking_check(event_name: str, event_date: str, event_location: str):
    """Checks the status of an event that requires booking."""
    if event_name.startswith("Space Needle"):
        return {"status": f"{event_name} is closed."}
    return {"status": f"{event_name} checked"}


def weather_impact_check(
    activity_name: str, activity_date: str, activity_location: str
):
    """Checks the status of an outdoor activity that may be impacted by weather."""
    return {"status": f"{activity_name} checked"}


# --- In-trip transit coordination (dynamic instruction callback) ---


def _get_event_time_as_destination(destin_json: dict[str, Any], default: str) -> str:
    match destin_json["event_type"]:
        case "flight":
            return destin_json["boarding_time"]
        case "hotel":
            return destin_json["check_in_time"]
        case "visit":
            return destin_json["start_time"]
        case _:
            return default


def _parse_as_origin(origin_json: dict[str, Any]):
    match origin_json["event_type"]:
        case "flight":
            return origin_json["arrival_airport"] + " Airport", origin_json["arrival_time"]
        case "hotel":
            return origin_json["description"] + " " + origin_json.get("address", ""), "any time"
        case "visit":
            return origin_json["description"] + " " + origin_json.get("address", ""), origin_json["end_time"]
        case "home":
            return origin_json.get("local_prefer_mode") + " from " + origin_json.get("address", ""), "any time"
        case _:
            return "Local in the region", "any time"


def _parse_as_destin(destin_json: dict[str, Any]):
    match destin_json["event_type"]:
        case "flight":
            return destin_json["departure_airport"] + " Airport", "An hour before " + destin_json["boarding_time"]
        case "hotel":
            return destin_json["description"] + " " + destin_json.get("address", ""), "any time"
        case "visit":
            return destin_json["description"] + " " + destin_json.get("address", ""), destin_json["start_time"]
        case "home":
            return destin_json.get("local_prefer_mode") + " to " + destin_json.get("address", ""), "any time"
        case _:
            return "Local in the region", "as soon as possible"


def _find_segment(profile: dict, itinerary: dict, current_datetime: str):
    """Find the current travel segment from itinerary based on datetime."""
    dt = datetime.fromisoformat(current_datetime)
    current_date = dt.strftime("%Y-%m-%d")
    current_time = dt.strftime("%H:%M")

    origin_json = profile["home"]
    destin_json = profile["home"]

    for day in itinerary.get("days", []):
        event_date = day["date"]
        for event in day["events"]:
            origin_json = destin_json
            destin_json = event
            event_time = _get_event_time_as_destination(destin_json, current_time)
            if event_date >= current_date and event_time >= current_time:
                break
        else:
            continue
        break

    travel_from, leave_by = _parse_as_origin(origin_json)
    travel_to, arrive_by = _parse_as_destin(destin_json)
    return travel_from, travel_to, leave_by, arrive_by


def transit_coordination(readonly_context: ReadonlyContext):
    """Dynamically generates an instruction for the day_of agent."""
    state = readonly_context.state
    if ITIN_KEY not in state:
        return NEED_ITINERARY_PROMPT

    itinerary = state[ITIN_KEY]
    profile = state[PROF_KEY]
    current_datetime = itinerary.get(START_DATE, "") + " 00:00"
    if state.get(ITIN_DATETIME, ""):
        current_datetime = state[ITIN_DATETIME]

    travel_from, travel_to, leave_by, arrive_by = _find_segment(
        profile, itinerary, current_datetime
    )

    return LOGISTIC_PROMPT_TEMPLATE.format(
        CURRENT_TIME=current_datetime,
        TRAVEL_FROM=travel_from,
        LEAVE_BY_TIME=leave_by,
        TRAVEL_TO=travel_to,
        ARRIVE_BY_TIME=arrive_by,
    )


# --- State initialization callback ---


def _set_initial_states(source: dict[str, Any], target: State | dict[str, Any]):
    if SYSTEM_TIME not in target:
        target[SYSTEM_TIME] = str(datetime.now())
    if ITIN_INITIALIZED not in target:
        target[ITIN_INITIALIZED] = True
        target.update(source)
        itinerary = source.get(ITIN_KEY, {})
        if itinerary:
            target[ITIN_START_DATE] = itinerary[START_DATE]
            target[ITIN_END_DATE] = itinerary[END_DATE]
            target[ITIN_DATETIME] = itinerary[START_DATE]


def _load_precreated_itinerary(callback_context: CallbackContext):
    """Load initial session state from a JSON scenario file."""
    data = {}
    with open(SAMPLE_SCENARIO_PATH) as f:
        data = json.load(f)
    _set_initial_states(data["state"], callback_context.state)


# ===================================================================
# Inspiration group  (place_agent, poi_agent -> inspiration_agent)
# ===================================================================

place_agent = (
    Agent("place_agent", MODEL)
    .describe("Suggests destination ideas given user preferences")
    .instruct(PLACE_AGENT_PROMPT)
    .disallow_transfer_to_parent(True)
    .disallow_transfer_to_peers(True)
    .output_schema(DestinationIdeas)
    .outputs("place")
    .generate_content_config(json_response_config)
)

poi_agent = (
    Agent("poi_agent", MODEL)
    .describe("Suggests activities and points of interest for a destination")
    .instruct(POI_AGENT_PROMPT)
    .disallow_transfer_to_parent(True)
    .disallow_transfer_to_peers(True)
    .output_schema(POISuggestions)
    .outputs("poi")
    .generate_content_config(json_response_config)
)

inspiration_agent = (
    Agent("inspiration_agent", MODEL)
    .describe(
        "A travel inspiration agent who inspires users and discovers their "
        "next vacations; Provides information about places, activities, interests"
    )
    .instruct(INSPIRATION_AGENT_PROMPT)
    .delegate(place_agent)
    .delegate(poi_agent)
    .tool(map_tool)
)

# ===================================================================
# Planning group  (flight/hotel/seat/room/itinerary -> planning_agent)
# ===================================================================

flight_search_agent = (
    Agent("flight_search_agent", MODEL)
    .describe("Help users find best flight deals")
    .instruct(FLIGHT_SEARCH_PROMPT)
    .disallow_transfer_to_parent(True)
    .disallow_transfer_to_peers(True)
    .output_schema(FlightsSelection)
    .outputs("flight")
    .generate_content_config(json_response_config)
)

flight_seat_selection_agent = (
    Agent("flight_seat_selection_agent", MODEL)
    .describe("Help users with the seat choices")
    .instruct(FLIGHT_SEAT_SELECTION_PROMPT)
    .disallow_transfer_to_parent(True)
    .disallow_transfer_to_peers(True)
    .output_schema(SeatsSelection)
    .outputs("seat")
    .generate_content_config(json_response_config)
)

hotel_search_agent = (
    Agent("hotel_search_agent", MODEL)
    .describe("Help users find hotel around a specific geographic area")
    .instruct(HOTEL_SEARCH_PROMPT)
    .disallow_transfer_to_parent(True)
    .disallow_transfer_to_peers(True)
    .output_schema(HotelsSelection)
    .outputs("hotel")
    .generate_content_config(json_response_config)
)

hotel_room_selection_agent = (
    Agent("hotel_room_selection_agent", MODEL)
    .describe("Help users with the room choices for a hotel")
    .instruct(HOTEL_ROOM_SELECTION_PROMPT)
    .disallow_transfer_to_parent(True)
    .disallow_transfer_to_peers(True)
    .output_schema(RoomsSelection)
    .outputs("room")
    .generate_content_config(json_response_config)
)

itinerary_agent = (
    Agent("itinerary_agent", MODEL)
    .describe("Create and persist a structured JSON representation of the itinerary")
    .instruct(ITINERARY_AGENT_PROMPT)
    .disallow_transfer_to_parent(True)
    .disallow_transfer_to_peers(True)
    .output_schema(Itinerary)
    .outputs("itinerary")
    .generate_content_config(json_response_config)
)

planning_agent = (
    Agent("planning_agent", MODEL)
    .describe(
        "Helps users with travel planning, complete a full itinerary for "
        "their vacation, finding best deals for flights and hotels."
    )
    .instruct(PLANNING_AGENT_PROMPT)
    .delegate(flight_search_agent)
    .delegate(flight_seat_selection_agent)
    .delegate(hotel_search_agent)
    .delegate(hotel_room_selection_agent)
    .delegate(itinerary_agent)
    .tool(memorize)
    .generate_content_config(GenerateContentConfig(temperature=0.1, top_p=0.5))
)

# ===================================================================
# Booking group  (reservation, payment_choice, process_payment -> booking_agent)
# ===================================================================

create_reservation = (
    Agent("create_reservation", MODEL)
    .describe("Create a reservation for the selected item.")
    .instruct(CONFIRM_RESERVATION_PROMPT)
)

payment_choice = (
    Agent("payment_choice", MODEL)
    .describe("Show the users available payment choices.")
    .instruct(PAYMENT_CHOICE_PROMPT)
)

process_payment = (
    Agent("process_payment", MODEL)
    .describe("Given a selected payment choice, processes the payment, completing the transaction.")
    .instruct(PROCESS_PAYMENT_PROMPT)
)

booking_agent = (
    Agent("booking_agent", MODEL)
    .describe(
        "Given an itinerary, complete the bookings of items by handling "
        "payment choices and processing."
    )
    .instruct(BOOKING_AGENT_PROMPT)
    .delegate(create_reservation)
    .delegate(payment_choice)
    .delegate(process_payment)
    .generate_content_config(GenerateContentConfig(temperature=0.0, top_p=0.5))
)

# ===================================================================
# Pre-trip group  (what_to_pack_agent, google_search -> pre_trip_agent)
# ===================================================================

google_search_grounding = (
    Agent("google_search_grounding", MODEL)
    .describe("An agent providing Google-search grounding capability")
    .instruct(SEARCH_GROUNDING_PROMPT)
    .tool(google_search)
)

what_to_pack_agent = (
    Agent("what_to_pack_agent", MODEL)
    .describe("Make suggestion on what to bring for the trip")
    .instruct(WHATTOPACK_PROMPT)
    .disallow_transfer_to_parent(True)
    .disallow_transfer_to_peers(True)
    .outputs("what_to_pack")
    .output_schema(PackingList)
)

pre_trip_agent = (
    Agent("pre_trip_agent", MODEL)
    .describe(
        "Given an itinerary, this agent keeps up to date and provides "
        "relevant travel information to the user before the trip."
    )
    .instruct(PRETRIP_AGENT_PROMPT)
    .tool(AgentTool(agent=google_search_grounding.build()))
    .delegate(what_to_pack_agent)
)

# ===================================================================
# In-trip group  (day_of_agent, trip_monitor_agent -> in_trip_agent)
# ===================================================================

day_of_agent = (
    Agent("day_of_agent", MODEL)
    .describe("Day_of agent is the agent handling the travel logistics of a trip.")
    .instruct(transit_coordination)
)

trip_monitor_agent = (
    Agent("trip_monitor_agent", MODEL)
    .describe("Monitor aspects of an itinerary and bring attention to items that necessitate changes")
    .instruct(TRIP_MONITOR_PROMPT)
    .tool(flight_status_check)
    .tool(event_booking_check)
    .tool(weather_impact_check)
    .outputs("daily_checks")
)

in_trip_agent = (
    Agent("in_trip_agent", MODEL)
    .describe("Provide information about what the users need as part of the tour.")
    .instruct(INTRIP_AGENT_PROMPT)
    .sub_agents([trip_monitor_agent.build()])
    .delegate(day_of_agent)
    .tool(memorize)
)

# ===================================================================
# Post-trip group
# ===================================================================

post_trip_agent = (
    Agent("post_trip_agent", MODEL)
    .describe(
        "A follow up agent to learn from user's experience; In turn "
        "improves the user's future trips planning and in-trip experience."
    )
    .instruct(POSTTRIP_AGENT_PROMPT)
    .tool(memorize)
)

# ===================================================================
# Root coordinator
# ===================================================================

root_agent = (
    Agent("root_agent", "gemini-2.0-flash-001")
    .describe("A Travel Concierge using the services of multiple sub-agents")
    .instruct(ROOT_AGENT_PROMPT)
    .sub_agents([
        inspiration_agent.build(),
        planning_agent.build(),
        booking_agent.build(),
        pre_trip_agent.build(),
        in_trip_agent.build(),
        post_trip_agent.build(),
    ])
    .before_agent(_load_precreated_itinerary)
    .build()
)

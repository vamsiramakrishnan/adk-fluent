# Travel Concierge

Full-lifecycle travel assistant with 6 specialist sub-agent groups orchestrated by a root coordinator: inspiration, planning, booking, pre-trip, in-trip, and post-trip. This is the largest ADK sample with 20+ agents across deeply nested directories.

## Architecture

Root coordinator delegates to 6 sub-agent groups, each containing their own specialist sub-agents:

```
root_agent (gemini-2.0-flash-001)
  |-- inspiration_agent       (delegates to place_agent, poi_agent; uses map_tool)
  |-- planning_agent           (delegates to flight_search, flight_seat, hotel_search, hotel_room, itinerary; uses memorize)
  |-- booking_agent            (delegates to create_reservation, payment_choice, process_payment)
  |-- pre_trip_agent           (delegates to what_to_pack_agent; uses google_search_grounding AgentTool)
  |-- in_trip_agent            (sub_agents: trip_monitor_agent; delegates to day_of_agent; uses memorize)
  |-- post_trip_agent          (uses memorize)
```

## Native ADK

Original uses 30+ files across 15+ directories:

```
travel_concierge/
├── __init__.py
├── agent.py
├── prompt.py
├── tracing.py
├── profiles/
│   ├── itinerary_empty_default.json
│   └── itinerary_seattle_example.json
├── shared_libraries/
│   ├── __init__.py
│   ├── constants.py
│   └── types.py
├── tools/
│   ├── __init__.py
│   ├── memory.py
│   ├── places.py
│   └── search.py
└── sub_agents/
    ├── __init__.py
    ├── inspiration/
    │   ├── __init__.py
    │   ├── agent.py
    │   └── prompt.py
    ├── planning/
    │   ├── __init__.py
    │   ├── agent.py
    │   └── prompt.py
    ├── booking/
    │   ├── __init__.py
    │   ├── agent.py
    │   └── prompt.py
    ├── pre_trip/
    │   ├── __init__.py
    │   ├── agent.py
    │   └── prompt.py
    ├── in_trip/
    │   ├── __init__.py
    │   ├── agent.py
    │   ├── prompt.py
    │   └── tools.py
    └── post_trip/
        ├── __init__.py
        ├── agent.py
        └── prompt.py
```

<details><summary>sub_agents/inspiration/agent.py (click to expand)</summary>

```python
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from travel_concierge.shared_libraries.types import (
    DestinationIdeas, POISuggestions, json_response_config,
)
from travel_concierge.sub_agents.inspiration import prompt
from travel_concierge.tools.places import map_tool

place_agent = Agent(
    model="gemini-2.5-flash",
    name="place_agent",
    instruction=prompt.PLACE_AGENT_INSTR,
    description="This agent suggests a few destination given some user preferences",
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
    output_schema=DestinationIdeas,
    output_key="place",
    generate_content_config=json_response_config,
)

poi_agent = Agent(
    model="gemini-2.5-flash",
    name="poi_agent",
    description="This agent suggests a few activities and points of interests given a destination",
    instruction=prompt.POI_AGENT_INSTR,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
    output_schema=POISuggestions,
    output_key="poi",
    generate_content_config=json_response_config,
)

inspiration_agent = Agent(
    model="gemini-2.5-flash",
    name="inspiration_agent",
    description="A travel inspiration agent...",
    instruction=prompt.INSPIRATION_AGENT_INSTR,
    tools=[AgentTool(agent=place_agent), AgentTool(agent=poi_agent), map_tool],
)
```

</details>

<details><summary>sub_agents/planning/agent.py (click to expand)</summary>

```python
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.genai.types import GenerateContentConfig
from travel_concierge.shared_libraries import types
from travel_concierge.sub_agents.planning import prompt
from travel_concierge.tools.memory import memorize

itinerary_agent = Agent(
    model="gemini-2.5-flash",
    name="itinerary_agent",
    description="Create and persist a structured JSON representation of the itinerary",
    instruction=prompt.ITINERARY_AGENT_INSTR,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
    output_schema=types.Itinerary,
    output_key="itinerary",
    generate_content_config=types.json_response_config,
)

hotel_room_selection_agent = Agent(
    model="gemini-2.5-flash",
    name="hotel_room_selection_agent",
    description="Help users with the room choices for a hotel",
    instruction=prompt.HOTEL_ROOM_SELECTION_INSTR,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
    output_schema=types.RoomsSelection,
    output_key="room",
    generate_content_config=types.json_response_config,
)

hotel_search_agent = Agent(
    model="gemini-2.5-flash",
    name="hotel_search_agent",
    description="Help users find hotel around a specific geographic area",
    instruction=prompt.HOTEL_SEARCH_INSTR,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
    output_schema=types.HotelsSelection,
    output_key="hotel",
    generate_content_config=types.json_response_config,
)

flight_seat_selection_agent = Agent(
    model="gemini-2.5-flash",
    name="flight_seat_selection_agent",
    description="Help users with the seat choices",
    instruction=prompt.FLIGHT_SEAT_SELECTION_INSTR,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
    output_schema=types.SeatsSelection,
    output_key="seat",
    generate_content_config=types.json_response_config,
)

flight_search_agent = Agent(
    model="gemini-2.5-flash",
    name="flight_search_agent",
    description="Help users find best flight deals",
    instruction=prompt.FLIGHT_SEARCH_INSTR,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
    output_schema=types.FlightsSelection,
    output_key="flight",
    generate_content_config=types.json_response_config,
)

planning_agent = Agent(
    model="gemini-2.5-flash",
    description="Helps users with travel planning...",
    name="planning_agent",
    instruction=prompt.PLANNING_AGENT_INSTR,
    tools=[
        AgentTool(agent=flight_search_agent),
        AgentTool(agent=flight_seat_selection_agent),
        AgentTool(agent=hotel_search_agent),
        AgentTool(agent=hotel_room_selection_agent),
        AgentTool(agent=itinerary_agent),
        memorize,
    ],
    generate_content_config=GenerateContentConfig(temperature=0.1, top_p=0.5),
)
```

</details>

<details><summary>sub_agents/booking/agent.py (click to expand)</summary>

```python
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.genai.types import GenerateContentConfig
from travel_concierge.sub_agents.booking import prompt

create_reservation = Agent(
    model="gemini-2.5-flash",
    name="create_reservation",
    description="Create a reservation for the selected item.",
    instruction=prompt.CONFIRM_RESERVATION_INSTR,
)

payment_choice = Agent(
    model="gemini-2.5-flash",
    name="payment_choice",
    description="Show the users available payment choices.",
    instruction=prompt.PAYMENT_CHOICE_INSTR,
)

process_payment = Agent(
    model="gemini-2.5-flash",
    name="process_payment",
    description="Given a selected payment choice, processes the payment.",
    instruction=prompt.PROCESS_PAYMENT_INSTR,
)

booking_agent = Agent(
    model="gemini-2.5-flash",
    name="booking_agent",
    description="Given an itinerary, complete the bookings...",
    instruction=prompt.BOOKING_AGENT_INSTR,
    tools=[
        AgentTool(agent=create_reservation),
        AgentTool(agent=payment_choice),
        AgentTool(agent=process_payment),
    ],
    generate_content_config=GenerateContentConfig(temperature=0.0, top_p=0.5),
)
```

</details>

<details><summary>sub_agents/pre_trip/agent.py (click to expand)</summary>

```python
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from travel_concierge.shared_libraries import types
from travel_concierge.sub_agents.pre_trip import prompt
from travel_concierge.tools.search import google_search_grounding

what_to_pack_agent = Agent(
    model="gemini-2.5-flash",
    name="what_to_pack_agent",
    description="Make suggestion on what to bring for the trip",
    instruction=prompt.WHATTOPACK_INSTR,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
    output_key="what_to_pack",
    output_schema=types.PackingList,
)

pre_trip_agent = Agent(
    model="gemini-2.5-flash",
    name="pre_trip_agent",
    description="Given an itinerary, this agent keeps up to date...",
    instruction=prompt.PRETRIP_AGENT_INSTR,
    tools=[google_search_grounding, AgentTool(agent=what_to_pack_agent)],
)
```

</details>

<details><summary>sub_agents/in_trip/agent.py (click to expand)</summary>

```python
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from travel_concierge.sub_agents.in_trip import prompt
from travel_concierge.sub_agents.in_trip.tools import (
    event_booking_check, flight_status_check,
    transit_coordination, weather_impact_check,
)
from travel_concierge.tools.memory import memorize

day_of_agent = Agent(
    model="gemini-2.5-flash",
    name="day_of_agent",
    description="Day_of agent is the agent handling the travel logistics.",
    instruction=transit_coordination,
)

trip_monitor_agent = Agent(
    model="gemini-2.5-flash",
    name="trip_monitor_agent",
    description="Monitor aspects of an itinerary...",
    instruction=prompt.TRIP_MONITOR_INSTR,
    tools=[flight_status_check, event_booking_check, weather_impact_check],
    output_key="daily_checks",
)

in_trip_agent = Agent(
    model="gemini-2.5-flash",
    name="in_trip_agent",
    description="Provide information about what the users need...",
    instruction=prompt.INTRIP_INSTR,
    sub_agents=[trip_monitor_agent],
    tools=[AgentTool(agent=day_of_agent), memorize],
)
```

</details>

<details><summary>sub_agents/post_trip/agent.py (click to expand)</summary>

```python
from google.adk.agents import Agent
from travel_concierge.sub_agents.post_trip import prompt
from travel_concierge.tools.memory import memorize

post_trip_agent = Agent(
    model="gemini-2.5-flash",
    name="post_trip_agent",
    description="A follow up agent to learn from user's experience...",
    instruction=prompt.POSTTRIP_INSTR,
    tools=[memorize],
)
```

</details>

<details><summary>tools/search.py -- google_search_grounding wrapper (click to expand)</summary>

```python
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.google_search_tool import google_search

_search_agent = Agent(
    model="gemini-2.5-flash",
    name="google_search_grounding",
    description="An agent providing Google-search grounding capability",
    instruction="""Answer the user's question directly using google_search grounding tool...""",
    tools=[google_search],
)

google_search_grounding = AgentTool(agent=_search_agent)
```

</details>

<details><summary>tools/memory.py -- memorize / forget / state init (click to expand)</summary>

```python
import json, os
from datetime import datetime
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import ToolContext
from travel_concierge.shared_libraries import constants

SAMPLE_SCENARIO_PATH = os.getenv(
    "TRAVEL_CONCIERGE_SCENARIO",
    "travel_concierge/profiles/itinerary_empty_default.json",
)

def memorize(key: str, value: str, tool_context: ToolContext):
    """Memorize pieces of information, one key-value pair at a time."""
    tool_context.state[key] = value
    return {"status": f'Stored "{key}": "{value}"'}

def _load_precreated_itinerary(callback_context: CallbackContext):
    """Sets up the initial state from a JSON file."""
    data = {}
    with open(SAMPLE_SCENARIO_PATH) as file:
        data = json.load(file)
    _set_initial_states(data["state"], callback_context.state)
```

</details>

<details><summary>tools/places.py -- Google Places API wrapper (click to expand)</summary>

```python
import os, requests
from google.adk.tools import ToolContext

class PlacesService:
    def find_place_from_text(self, query: str) -> dict[str, str]:
        # ... Google Places API call ...
        pass

places_service = PlacesService()

def map_tool(key: str, tool_context: ToolContext):
    """Inspect POIs under the key in state and verify lat/lon via Map API."""
    # ... iterates state[key]["places"], calls Places API ...
    pass
```

</details>

<details><summary>shared_libraries/types.py -- 20+ Pydantic models (click to expand)</summary>

```python
from google.genai import types
from pydantic import BaseModel, Field

json_response_config = types.GenerateContentConfig(
    response_mime_type="application/json"
)

class Room(BaseModel):
    is_available: bool
    price_in_usd: int
    room_type: str

class RoomsSelection(BaseModel):
    rooms: list[Room]

class Hotel(BaseModel):
    name: str
    address: str
    check_in_time: str
    check_out_time: str
    thumbnail: str
    price: int

class HotelsSelection(BaseModel):
    hotels: list[Hotel]

# ... Seat, SeatsSelection, Flight, FlightsSelection,
# Destination, DestinationIdeas, POI, POISuggestions,
# AttractionEvent, FlightEvent, HotelEvent, ItineraryDay,
# Itinerary, UserProfile, PackingList ...
```

</details>

<details><summary>sub_agents/in_trip/tools.py -- transit coordination logic (click to expand)</summary>

```python
from datetime import datetime
from google.adk.agents.readonly_context import ReadonlyContext
from travel_concierge.shared_libraries import constants
from travel_concierge.sub_agents.in_trip import prompt

def flight_status_check(flight_number, flight_date, checkin_time, departure_time):
    return {"status": f"Flight {flight_number} checked"}

def event_booking_check(event_name, event_date, event_location):
    if event_name.startswith("Space Needle"):
        return {"status": f"{event_name} is closed."}
    return {"status": f"{event_name} checked"}

def weather_impact_check(activity_name, activity_date, activity_location):
    return {"status": f"{activity_name} checked"}

def transit_coordination(readonly_context: ReadonlyContext):
    """Dynamically generates an instruction for the day_of agent."""
    # ... 100+ lines of segment-finding logic ...
    pass
```

</details>

```python
# travel_concierge/agent.py (root)
from google.adk.agents import Agent
from travel_concierge import prompt
from travel_concierge.sub_agents.booking.agent import booking_agent
from travel_concierge.sub_agents.in_trip.agent import in_trip_agent
from travel_concierge.sub_agents.inspiration.agent import inspiration_agent
from travel_concierge.sub_agents.planning.agent import planning_agent
from travel_concierge.sub_agents.post_trip.agent import post_trip_agent
from travel_concierge.sub_agents.pre_trip.agent import pre_trip_agent
from travel_concierge.tools.memory import _load_precreated_itinerary

root_agent = Agent(
    model="gemini-2.0-flash-001",
    name="root_agent",
    description="A Travel Concierge using the services of multiple sub-agents",
    instruction=prompt.ROOT_AGENT_INSTR,
    sub_agents=[
        inspiration_agent,
        planning_agent,
        booking_agent,
        pre_trip_agent,
        in_trip_agent,
        post_trip_agent,
    ],
    before_agent_callback=_load_precreated_itinerary,
)
```

## Fluent API

3 files, flat directory:

```
travel_concierge/
├── __init__.py
├── agent.py
└── prompt.py
```

```python
# agent.py
from adk_fluent import Agent
from dotenv import load_dotenv
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import ToolContext, google_search
from google.adk.tools.agent_tool import AgentTool
from google.genai.types import GenerateContentConfig
from pydantic import BaseModel, Field

from .prompt import (
    BOOKING_AGENT_PROMPT, CONFIRM_RESERVATION_PROMPT,
    FLIGHT_SEARCH_PROMPT, FLIGHT_SEAT_SELECTION_PROMPT,
    HOTEL_ROOM_SELECTION_PROMPT, HOTEL_SEARCH_PROMPT,
    INSPIRATION_AGENT_PROMPT, INTRIP_AGENT_PROMPT,
    ITINERARY_AGENT_PROMPT, LOGISTIC_PROMPT_TEMPLATE,
    NEED_ITINERARY_PROMPT, PAYMENT_CHOICE_PROMPT,
    PLACE_AGENT_PROMPT, PLANNING_AGENT_PROMPT,
    POI_AGENT_PROMPT, POSTTRIP_AGENT_PROMPT,
    PRETRIP_AGENT_PROMPT, PROCESS_PAYMENT_PROMPT,
    ROOT_AGENT_PROMPT, SEARCH_GROUNDING_PROMPT,
    TRIP_MONITOR_PROMPT, WHATTOPACK_PROMPT,
)

load_dotenv()
MODEL = "gemini-2.5-flash"

# Pydantic schemas, tools, and callbacks are inline in agent.py
# (see full source for details)

# --- Inspiration group ---

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
    .describe("A travel inspiration agent...")
    .instruct(INSPIRATION_AGENT_PROMPT)
    .delegate(place_agent)
    .delegate(poi_agent)
    .tool(map_tool)
)

# --- Planning group ---

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

# ... (flight_seat, hotel_search, hotel_room, itinerary agents similar) ...

planning_agent = (
    Agent("planning_agent", MODEL)
    .describe("Helps users with travel planning...")
    .instruct(PLANNING_AGENT_PROMPT)
    .delegate(flight_search_agent)
    .delegate(flight_seat_selection_agent)
    .delegate(hotel_search_agent)
    .delegate(hotel_room_selection_agent)
    .delegate(itinerary_agent)
    .tool(memorize)
    .generate_content_config(GenerateContentConfig(temperature=0.1, top_p=0.5))
)

# --- Booking group ---

booking_agent = (
    Agent("booking_agent", MODEL)
    .describe("Complete the bookings by handling payment choices and processing.")
    .instruct(BOOKING_AGENT_PROMPT)
    .delegate(create_reservation)
    .delegate(payment_choice)
    .delegate(process_payment)
    .generate_content_config(GenerateContentConfig(temperature=0.0, top_p=0.5))
)

# --- Pre-trip, In-trip, Post-trip groups ---

pre_trip_agent = (
    Agent("pre_trip_agent", MODEL)
    .describe("Provides relevant travel information before the trip.")
    .instruct(PRETRIP_AGENT_PROMPT)
    .tool(AgentTool(agent=google_search_grounding.build()))
    .delegate(what_to_pack_agent)
)

in_trip_agent = (
    Agent("in_trip_agent", MODEL)
    .describe("Provide information during the tour.")
    .instruct(INTRIP_AGENT_PROMPT)
    .sub_agents([trip_monitor_agent.build()])
    .delegate(day_of_agent)
    .tool(memorize)
)

post_trip_agent = (
    Agent("post_trip_agent", MODEL)
    .describe("Learn from user's experience for future improvements.")
    .instruct(POSTTRIP_AGENT_PROMPT)
    .tool(memorize)
)

# --- Root coordinator ---

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
```

## What Changed

- 14x `AgentTool(agent=...)` wrapping calls replaced by `.delegate()`
- `output_key=` replaced by `.outputs()`
- `instruction=` replaced by `.instruct()`
- `description=` replaced by `.describe()`
- 30+ files across 15+ directories collapsed to 3 files in 1 directory
- No `__init__.py` re-export chain needed (eliminated 8 init files)
- No separate sub-agent packages for each of the 6 groups
- `shared_libraries/types.py`, `shared_libraries/constants.py` inlined
- `tools/memory.py`, `tools/places.py`, `tools/search.py` consolidated into agent.py
- All 7 separate `prompt.py` files merged into a single `prompt.py`
- Cross-package imports (`from travel_concierge.sub_agents.booking.agent import ...`) eliminated
- State constants, Pydantic schemas, and tool functions colocated with agent definitions

## Metrics

| Metric                       | Native | Fluent | Reduction |
| ---------------------------- | ------ | ------ | --------- |
| Agent definition files       | 7      | 1      | 86%       |
| Prompt files                 | 7      | 1      | 86%       |
| Total Python files           | 22     | 3      | 86%       |
| Directories                  | 15     | 1      | 93%       |
| `__init__.py` files          | 9      | 1      | 89%       |
| `import` statements          | 50+    | 22     | 56%       |
| `AgentTool(agent=...)` calls | 14     | 0      | 100%      |

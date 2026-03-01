# Capture and Route: IT Helpdesk Triage

Real-world use case: IT helpdesk ticket capture and routing system. Captures
incoming messages into state, classifies urgency, and routes to appropriate
support tiers.

In other frameworks: LangGraph requires custom state capture via TypedDict
updates and conditional_edges for routing. adk-fluent uses S.capture() for
state injection and Route() for declarative branching.

Pipeline topology:
    S.capture("ticket")
        >> triage [save_as: priority]
        >> Route("priority")
            ├─ "p1" -> incident_commander
            ├─ "p2" -> senior_support
            └─ else -> support_bot

:::{admonition} Why this matters
:class: important
User messages arrive as unstructured text, but pipelines need structured state for routing and template injection. `S.capture()` copies the user message into a named state key, making it available to downstream agents through instruction templates. Combined with `Route()`, this enables the pattern: capture the message, classify it, route to the right specialist -- all with the original message preserved for the specialist to reference.
:::

:::{warning} Without this
Without state capture, the user's original message is only available through conversation history -- which means the specialist agent must parse through all previous messages to find it. If you strip history with `C.none()` (for efficiency), the specialist can't see the user's message at all. `S.capture()` solves this by putting the message in state where any agent can access it regardless of context settings.
:::

:::{tip} What you'll learn
How to capture user input into state and route on it.
:::

_Source: `50_capture_and_route.py`_

::::{tab-set}
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, S
from adk_fluent._routing import Route
from adk_fluent.testing import check_contracts

MODEL = "gemini-2.5-flash"

# IT Helpdesk: capture ticket → classify priority → route to team
helpdesk = (
    S.capture("ticket")
    >> Agent("triage")
    .model(MODEL)
    .instruct(
        "You are an IT helpdesk triage agent.\n"
        "Read the support ticket and classify it.\n"
        "Ticket: {ticket}\n"
        "Output the priority level: p1, p2, or p3."
    )
    .writes("priority")
    >> Route("priority")
    .eq(
        "p1",
        Agent("incident_commander")
        .model(MODEL)
        .instruct(
            "CRITICAL INCIDENT.\nOriginal ticket: {ticket}\nCoordinate immediate response. Page on-call engineer."
        ),
    )
    .eq(
        "p2",
        Agent("senior_support")
        .model(MODEL)
        .instruct("Priority ticket.\nTicket: {ticket}\nInvestigate and provide a resolution plan within 4 hours."),
    )
    .otherwise(
        Agent("support_bot")
        .model(MODEL)
        .instruct("Routine support request.\nTicket: {ticket}\nProvide self-service instructions or FAQ links.")
    )
)

# Verify data contracts before deployment
issues = check_contracts(helpdesk.to_ir())
contract_errors = [i for i in issues if isinstance(i, dict) and i.get("level") == "error"]

built = helpdesk.build()
```
:::
:::{tab-item} Native ADK
```python
# In native ADK, capturing the user's message into state for downstream
# agents requires writing a custom BaseAgent subclass:
#
# class CaptureUserMessage(BaseAgent):
#     async def _run_async_impl(self, ctx):
#         for event in reversed(ctx.session.events):
#             if event.author == "user":
#                 ctx.session.state["ticket"] = event.content.parts[0].text
#                 break
#
# Then manually wiring it as the first step in a SequentialAgent.
# Route-based dispatch requires another custom agent with if/elif logic.
```
:::
:::{tab-item} Architecture
```mermaid
graph TD
    n1[["capture_ticket_then_triage_routed (sequence)"]]
    n2>"capture_ticket capture(ticket)"]
    n3["triage"]
    n4{"route_priority (route)"}
    n5["incident_commander"]
    n6["senior_support"]
    n7["support_bot"]
    n4 --> n5
    n4 --> n6
    n4 -.-> n7
    n2 --> n3
    n3 --> n4
    n3 -. "priority" .-> n4
    n2 -. "ticket" .-> n3
    n2 -. "ticket" .-> n5
    n2 -. "ticket" .-> n6
    n2 -. "ticket" .-> n7
```
:::
::::

## Equivalence

```python
# Contract checking passes — all {ticket}, {priority} resolve
assert len(contract_errors) == 0

# Pipeline builds with capture agent first
from adk_fluent._base import CaptureAgent

assert isinstance(built.sub_agents[0], CaptureAgent)
assert built.sub_agents[0].name == "capture_ticket"

# Triage agent is second
assert built.sub_agents[1].name == "triage"

# Full pipeline builds
assert built is not None
assert len(built.sub_agents) >= 3
```

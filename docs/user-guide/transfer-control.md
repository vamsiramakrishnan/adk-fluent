# Transfer Control

In multi-agent systems, the LLM decides when to hand off a conversation to another agent. Transfer control flags let you constrain which agents are valid transfer targets, shaping how conversations flow through your agent hierarchy.

## Overview

ADK supports three transfer directions:

- **Parent to child** -- A coordinator agent transfers to one of its `sub_agents`. This is always allowed; you cannot prevent an agent from delegating to its own children.
- **Child to parent** -- A specialist agent transfers back to its parent after completing work. Controlled by `disallow_transfer_to_parent`.
- **Peer to peer** -- A sibling agent laterally transfers to another child of the same parent. Controlled by `disallow_transfer_to_peers`.

Under the hood, ADK injects a `transfer_to_agent` tool into the LLM's tool list. The tool uses enum constraints so the LLM can only name valid transfer targets -- it cannot hallucinate agent names that do not exist. The list of valid targets is computed by `_get_transfer_targets()` each turn:

- Sub-agents are **always** included
- Parent is included unless `disallow_transfer_to_parent=True`
- Peers are included unless `disallow_transfer_to_peers=True`

## Transfer Control Flags

### `.disallow_transfer_to_parent(True)`

Prevents this agent's LLM from transferring control back to its parent agent.

```python
from adk_fluent import Agent

specialist = (
    Agent("billing", "gemini-2.5-flash")
    .instruct("Handle billing inquiries. Resolve the issue completely.")
    .disallow_transfer_to_parent(True)
)
```

This flag has a subtle but important secondary effect: when the agent finishes responding, ADK forces a handoff back to the parent on the next turn. Without this flag, the user could continue chatting with the specialist indefinitely. With it, the specialist completes its task and control automatically returns to the parent.

This makes `disallow_transfer_to_parent(True)` ideal for focused specialists that should answer one question and return, rather than becoming a conversational dead end.

### `.disallow_transfer_to_peers(True)`

Prevents this agent's LLM from laterally transferring to sibling agents (other children of the same parent).

```python
specialist = (
    Agent("billing", "gemini-2.5-flash")
    .instruct("Handle billing inquiries.")
    .disallow_transfer_to_peers(True)
)
```

Without this flag, a billing agent could decide to transfer the user to a technical support agent if it thought the question was better suited there. Setting `disallow_transfer_to_peers(True)` prevents this -- only the coordinator (parent) decides routing.

### `.isolate()`

A convenience method that sets both flags to `True`. This is the most common pattern for specialist agents:

```python
specialist = (
    Agent("billing", "gemini-2.5-flash")
    .instruct("Handle billing inquiries.")
    .isolate()
)

# Equivalent to:
specialist = (
    Agent("billing", "gemini-2.5-flash")
    .instruct("Handle billing inquiries.")
    .disallow_transfer_to_parent(True)
    .disallow_transfer_to_peers(True)
)
```

Use `.isolate()` for any agent that should complete its task and return to the coordinator. The agent cannot wander off to a sibling and cannot keep the conversation going -- it answers and hands back.

## Control Matrix

All four combinations of the two flags and their resulting behavior:

| `disallow_transfer_to_parent` | `disallow_transfer_to_peers` | Behavior |
|:----:|:----:|------|
| `False` | `False` | **Full transfer.** Agent can transfer to parent, siblings, and its own children. Default behavior. |
| `True` | `False` | **Peers only.** Agent can transfer to siblings but not back to parent. Useful for peer-to-peer handoff chains. |
| `False` | `True` | **Parent only.** Agent can transfer back to parent but not to siblings. The coordinator decides all lateral routing. |
| `True` | `True` | **Isolated.** No outbound transfers. Agent completes its task and control returns to parent automatically. This is what `.isolate()` sets. |

## Common Patterns

### Coordinator + Specialists

The most common multi-agent pattern. A coordinator routes incoming requests to specialist agents, each isolated so they complete their task and return:

```python
from adk_fluent import Agent

billing = (
    Agent("billing", "gemini-2.5-flash")
    .describe("Handles billing questions, invoices, and payment issues")
    .instruct("You are a billing specialist. Resolve the customer's billing issue.")
    .isolate()
)

technical = (
    Agent("technical", "gemini-2.5-flash")
    .describe("Handles technical support, troubleshooting, and bugs")
    .instruct("You are a technical support specialist. Diagnose and resolve the issue.")
    .isolate()
)

coordinator = (
    Agent("coordinator", "gemini-2.5-flash")
    .instruct(
        "You are a customer service coordinator. "
        "Route the customer to the appropriate specialist based on their request."
    )
    .sub_agent(billing)
    .sub_agent(technical)
)
```

The coordinator's LLM sees a `transfer_to_agent` tool with two options: `billing` and `technical`. Each specialist handles the request and returns control to the coordinator, which can then route to another specialist or respond directly.

### Hub and Spoke

A central agent delegates to multiple specialists who each have their own sub-agents. The hub uses default transfer settings (full transfer), while leaf specialists use `.isolate()`:

```python
from adk_fluent import Agent

# Leaf specialists -- isolated
flight_search = (
    Agent("flight_search", "gemini-2.5-flash")
    .describe("Search for flight options")
    .instruct("Find flights matching the user's criteria.")
    .isolate()
)

hotel_search = (
    Agent("hotel_search", "gemini-2.5-flash")
    .describe("Search for hotel options")
    .instruct("Find hotels matching the user's criteria.")
    .isolate()
)

# Mid-level coordinator -- default transfer (can go to parent or peers)
planning = (
    Agent("planning", "gemini-2.5-flash")
    .describe("Handles travel planning: flights, hotels, itineraries")
    .instruct("Help the user plan their trip.")
    .sub_agent(flight_search)
    .sub_agent(hotel_search)
)

support = (
    Agent("support", "gemini-2.5-flash")
    .describe("Handles post-booking support and changes")
    .instruct("Help the user with booking changes and support requests.")
    .isolate()
)

# Root hub
root = (
    Agent("concierge", "gemini-2.5-flash")
    .instruct("You are a travel concierge. Route to planning or support.")
    .sub_agent(planning)
    .sub_agent(support)
)
```

### Sequential Handoff

Peers transfer to each other in sequence, using `disallow_transfer_to_parent(True)` with `disallow_transfer_to_peers(False)` so they can hand off laterally but not escape back to the coordinator mid-sequence:

```python
from adk_fluent import Agent

intake = (
    Agent("intake", "gemini-2.5-flash")
    .describe("Gathers initial information from the customer")
    .instruct(
        "Collect the customer's name, account number, and issue description. "
        "Then transfer to the diagnosis agent."
    )
    .disallow_transfer_to_parent(True)
)

diagnosis = (
    Agent("diagnosis", "gemini-2.5-flash")
    .describe("Diagnoses the root cause of the issue")
    .instruct(
        "Analyze the customer's issue and determine the root cause. "
        "Then transfer to the resolution agent."
    )
    .disallow_transfer_to_parent(True)
)

resolution = (
    Agent("resolution", "gemini-2.5-flash")
    .describe("Resolves the issue and confirms with the customer")
    .instruct("Apply the fix and confirm resolution with the customer.")
    .isolate()  # End of the chain -- return to coordinator
)

workflow = (
    Agent("support_workflow", "gemini-2.5-flash")
    .instruct("Route the customer through the support workflow.")
    .sub_agent(intake)
    .sub_agent(diagnosis)
    .sub_agent(resolution)
)
```

The intake agent can transfer to diagnosis or resolution (peers), but not back to the coordinator. The resolution agent is fully isolated -- once it finishes, control returns to the coordinator.

## Flow Selection

ADK selects the execution flow for each agent based on its transfer configuration and sub-agents:

- **AutoFlow** -- Used when the agent has at least one valid transfer target (sub-agents, parent, or peers). The LLM receives the `transfer_to_agent` tool and can decide to hand off.
- **SingleFlow** -- Used when the agent has no valid transfer targets at all. This happens when both `disallow_transfer_to_parent=True` and `disallow_transfer_to_peers=True` **and** the agent has no `sub_agents`. The LLM receives no transfer tool and simply responds.

```
Has sub_agents?
  Yes -> AutoFlow (can always transfer to children)
  No  -> Are both flags True?
           Yes -> SingleFlow (no transfer capability)
           No  -> AutoFlow (can transfer to parent and/or peers)
```

This means `.isolate()` on a leaf agent (no children) produces the simplest execution path: the agent processes the request, responds, and returns. No transfer tool is injected, so the LLM cannot even attempt a transfer.

If an isolated agent **does** have sub-agents, it still uses AutoFlow because it can delegate to its children. It just cannot transfer to its parent or peers.

## Complete Example

A customer service system with a coordinator routing to three specialist agents. Each specialist is isolated so it handles its domain and returns:

### Native ADK

```python
from google.adk.agents.llm_agent import LlmAgent

billing = LlmAgent(
    name="billing",
    model="gemini-2.5-flash",
    description="Handles billing questions, invoices, refunds, and payment issues",
    instruction=(
        "You are a billing specialist for Acme Corp. "
        "Help the customer with their billing issue. "
        "Look up their account, explain charges, and process refunds if needed."
    ),
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)

technical = LlmAgent(
    name="technical",
    model="gemini-2.5-flash",
    description="Handles technical support, troubleshooting, and bug reports",
    instruction=(
        "You are a technical support specialist for Acme Corp. "
        "Diagnose the customer's technical issue. "
        "Walk them through troubleshooting steps or escalate if needed."
    ),
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)

general = LlmAgent(
    name="general",
    model="gemini-2.5-flash",
    description="Handles general inquiries, account info, and FAQs",
    instruction=(
        "You are a general support agent for Acme Corp. "
        "Answer common questions about products, policies, and account details."
    ),
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)

coordinator = LlmAgent(
    name="coordinator",
    model="gemini-2.5-flash",
    instruction=(
        "You are the front-line coordinator for Acme Corp customer service. "
        "Greet the customer, understand their need, and route them to the "
        "appropriate specialist: billing, technical, or general."
    ),
    sub_agents=[billing, technical, general],
)
```

### adk-fluent

```python
from adk_fluent import Agent

billing = (
    Agent("billing", "gemini-2.5-flash")
    .describe("Handles billing questions, invoices, refunds, and payment issues")
    .instruct(
        "You are a billing specialist for Acme Corp. "
        "Help the customer with their billing issue. "
        "Look up their account, explain charges, and process refunds if needed."
    )
    .isolate()
)

technical = (
    Agent("technical", "gemini-2.5-flash")
    .describe("Handles technical support, troubleshooting, and bug reports")
    .instruct(
        "You are a technical support specialist for Acme Corp. "
        "Diagnose the customer's technical issue. "
        "Walk them through troubleshooting steps or escalate if needed."
    )
    .isolate()
)

general = (
    Agent("general", "gemini-2.5-flash")
    .describe("Handles general inquiries, account info, and FAQs")
    .instruct(
        "You are a general support agent for Acme Corp. "
        "Answer common questions about products, policies, and account details."
    )
    .isolate()
)

coordinator = (
    Agent("coordinator", "gemini-2.5-flash")
    .instruct(
        "You are the front-line coordinator for Acme Corp customer service. "
        "Greet the customer, understand their need, and route them to the "
        "appropriate specialist: billing, technical, or general."
    )
    .sub_agent(billing)
    .sub_agent(technical)
    .sub_agent(general)
    .build()
)
```

The fluent version replaces the repetitive `disallow_transfer_to_parent=True, disallow_transfer_to_peers=True` with a single `.isolate()` call on each specialist. The `.describe()` values are important -- they become part of the `transfer_to_agent` tool's descriptions, helping the coordinator LLM make good routing decisions.

## Tips

- **Always set `.describe()` on sub-agents.** The description is included in the transfer tool's metadata. A clear description helps the coordinator LLM pick the right specialist.
- **Use `.isolate()` by default for specialists.** Unless you have a specific reason for peer-to-peer transfer, isolated specialists produce the most predictable routing behavior.
- **Coordinators should not be isolated.** A coordinator needs full transfer capability to delegate to its children and, if it is itself a sub-agent, to return to its own parent.
- **Test transfer behavior with `.events()`.** Stream the raw events to see which agent handles each turn and when transfers occur:

```python
import asyncio
from adk_fluent import Agent

coordinator = (
    Agent("coordinator", "gemini-2.5-flash")
    .instruct("Route to billing or technical support.")
    .sub_agent(
        Agent("billing", "gemini-2.5-flash")
        .describe("Billing support")
        .instruct("Handle billing.")
        .isolate()
    )
    .sub_agent(
        Agent("technical", "gemini-2.5-flash")
        .describe("Technical support")
        .instruct("Handle technical issues.")
        .isolate()
    )
)

async def main():
    async for event in coordinator.events("I was double-charged on my last invoice"):
        if event.content and event.content.parts:
            agent = getattr(event, 'author', 'unknown')
            text = event.content.parts[0].text or ""
            if text:
                print(f"[{agent}] {text[:100]}")

asyncio.run(main())
```

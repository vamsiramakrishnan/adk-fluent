# E-Commerce Order Pipeline — Every Primitive in One System

> **Modules in play:** `tap()` observation, `expect()` assertions, `gate()`
> human-in-the-loop, `Route` deterministic branching, `S.*` state transforms,
> `C.none()` context isolation, `>>` sequential

## The Real-World Problem

Your e-commerce platform processes three order types (digital, physical, custom)
through different fulfillment paths. You need fraud detection that pauses for
human review on high-risk orders, data contracts that catch missing fields before
they reach the payment processor, state transforms that compute shipping costs
without an LLM call, and monitoring hooks that observe order flow without
slowing it down.

This is the kitchen-sink scenario — it touches every primitive adk-fluent offers.
If you understand this pipeline, you understand the full toolkit.

## The Fluent Solution

```python
from adk_fluent import Agent, Pipeline, S, C, tap, expect, gate
from adk_fluent._routing import Route

MODEL = "gemini-2.5-flash"

# Fraud detection gate — pauses pipeline for human review
fraud_gate = gate(
    lambda s: s.get("fraud_score") == "high",
    message="Potential fraud detected. Manual review required.",
    gate_key="fraud_review_gate",
)

# THE SYMPHONY: defaults → classify → route → observe → assert → compute → notify
ecommerce_pipeline = (
    # Set default values (zero-cost, no LLM)
    S.default(currency="USD", shipping_method="standard")
    # Classify order type
    >> Agent("order_classifier", MODEL)
       .instruct("Classify the order type.")
       .writes("order_type")
    # Route to fulfillment handler by type
    >> Route("order_type")
       .eq("digital", Agent("digital_delivery", MODEL)
           .instruct("Deliver digital product.").writes("delivery_status"))
       .eq("physical", Agent("warehouse_pick", MODEL)
           .instruct("Pick and pack from warehouse.").writes("delivery_status"))
       .otherwise(Agent("custom_handler", MODEL)
           .instruct("Handle custom order.").writes("delivery_status"))
    # Observe routing result (zero-cost monitoring)
    >> tap(lambda s: None)
    # Assert contract: fulfillment must set delivery_status
    >> expect(lambda s: "delivery_status" in s,
             "Fulfillment must set delivery_status")
    # Compute shipping ETA (zero-cost, no LLM)
    >> S.compute(eta_days=lambda s: 1 if s.get("order_type") == "digital" else 5)
    # Send confirmation
    >> Agent("notification_sender", MODEL)
       .instruct("Send order confirmation email.")
       .writes("confirmation_id")
)
```

## The Interplay Breakdown

**Why `S.default()` at the start?**
Optional fields like `currency` and `shipping_method` need fallback values.
Without defaults, downstream agents either crash on missing keys or produce
garbage. `S.default()` is a zero-cost state transform — no LLM call, just
dictionary manipulation.

**Why `expect()` between fulfillment and notification?**
The contract is simple: fulfillment *must* set `delivery_status`. If a new
fulfillment handler forgets this key, `expect()` raises immediately instead
of letting the notification agent send "Your order status is: None." This is
a build-time safety net — think of it as an assertion in your pipeline topology.

**Why `tap()` for monitoring?**
`tap()` executes a function but never modifies state. It's perfect for
analytics (counting orders by type, measuring fulfillment latency) without
risking side effects. Unlike adding a "logging agent" (which costs an LLM
call), `tap` is free.

**Why `S.compute()` for ETA?**
Computing "digital = 1 day, physical = 5 days" doesn't need an LLM — it's
arithmetic. `S.compute()` runs a plain Python function as a pipeline step.
This is the pattern: use LLM agents for reasoning, plain functions for
computation.

## Pipeline Topology

```
S.default(currency, shipping)
    ──► order_classifier
        ──► Route("order_type")
            ├─ "digital"  → digital_delivery
            ├─ "physical" → warehouse_pick
            └─ otherwise  → custom_handler
        ──► tap(monitor)
            ──► expect(delivery_status exists)
                ──► S.compute(eta_days)
                    ──► notification_sender
```

## Running on Different Backends

::::{tab-set}
:::{tab-item} ADK (default)
```python
response = ecommerce_pipeline.ask("Order #12345 — where is my package?")
```
:::
:::{tab-item} Temporal (in dev)
```python
from temporalio.client import Client
client = await Client.connect("localhost:7233")

# tap(), expect(), Route() are all deterministic — replay-safe
# Each agent step is a checkpointed Activity
durable = ecommerce_pipeline.engine("temporal", client=client, task_queue="orders")
response = await durable.ask_async("Order #12345 — where is my package?")
```
:::
:::{tab-item} asyncio (in dev)
```python
response = await ecommerce_pipeline.engine("asyncio").ask_async("Order #12345")
```
:::
::::

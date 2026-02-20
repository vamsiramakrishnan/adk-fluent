# Primitives Showcase: E-Commerce Order Pipeline Using All Primitives

*How to compose agents into a sequential pipeline.*

_Source: `43_primitives_showcase.py`_

::::{tab-set}
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Pipeline, S, tap, expect, gate
from adk_fluent._routing import Route
from adk_fluent.workflow import Loop

MODEL = "gemini-2.5-flash"

# --- 1. tap: observe state for monitoring without mutating ---

order_events = []
order_parser = Agent("order_parser", MODEL).instruct("Parse the incoming order JSON.").outputs("order_type")
pipeline_with_tap = order_parser >> tap(lambda s: order_events.append(s.get("order_type")))
assert isinstance(pipeline_with_tap, Pipeline)

# tap via method syntax (same result)
pipeline_method = order_parser.tap(lambda s: order_events.append(s.get("order_type")))
assert isinstance(pipeline_method, Pipeline)

# --- 2. expect: assert data contracts between processing stages ---

inventory_checker = Agent("inventory_checker", MODEL).instruct("Check stock availability.").outputs("in_stock")
payment_processor = Agent("payment_processor", MODEL).instruct("Process payment.")

pipeline_with_expect = (
    inventory_checker
    >> expect(lambda s: s.get("in_stock") == "yes", "Item must be in stock before processing payment")
    >> payment_processor
)
assert isinstance(pipeline_with_expect, Pipeline)
built = pipeline_with_expect.build()
assert len(built.sub_agents) == 3  # inventory_checker, expect, payment_processor

# --- 3. gate: human-in-the-loop for high-value orders ---

fraud_gate = gate(
    lambda s: s.get("fraud_score") == "high",
    message="Potential fraud detected. Manual review required.",
    gate_key="fraud_review_gate",
)
fulfillment_agent = Agent("fulfillment", MODEL).instruct("Ship the order to the customer.")

pipeline_with_gate = (
    Agent("fraud_detector", MODEL).instruct("Score fraud risk.").outputs("fraud_score")
    >> fraud_gate
    >> fulfillment_agent
)
assert isinstance(pipeline_with_gate, Pipeline)
built_gate = pipeline_with_gate.build()
assert len(built_gate.sub_agents) == 3

# --- 4. Route: deterministic order routing by type ---

standard_handler = Agent("standard_handler", MODEL).instruct("Process standard delivery order.")
express_handler = Agent("express_handler", MODEL).instruct("Process express delivery order.")
pickup_handler = Agent("pickup_handler", MODEL).instruct("Process store pickup order.")

order_route = (
    Route("order_type").eq("standard", standard_handler).eq("express", express_handler).otherwise(pickup_handler)
)

routed_pipeline = order_parser >> order_route
assert isinstance(routed_pipeline, Pipeline)
built_route = routed_pipeline.build()
assert len(built_route.sub_agents) == 2  # order_parser + route_agent

# Route with .when() for complex multi-condition logic
priority_route = (
    Route()
    .when(lambda s: s.get("total", 0) > 500 and s.get("membership") == "premium", express_handler)
    .when(lambda s: s.get("total", 0) > 200, standard_handler)
    .otherwise(pickup_handler)
)
assert len(priority_route._rules) == 2
assert priority_route._default is pickup_handler

# --- 5. S.*: state transforms for order data management ---

# S.pick -- extract only the fields needed for the shipping label
pick_step = S.pick("customer_name", "shipping_address")
assert callable(pick_step)

# S.drop -- remove internal processing fields before customer notification
drop_step = S.drop("_internal_score", "_processing_log")
assert callable(drop_step)

# S.rename -- normalize field names between systems
rename_step = S.rename(customer_email="email_address")
assert callable(rename_step)

# S.default -- set fallback values for optional order fields
default_step = S.default(currency="USD", shipping_method="standard")
assert callable(default_step)

# S.merge -- combine item subtotals into a single order total
merge_step = S.merge("subtotal", "tax", into="order_financials")
assert callable(merge_step)

# S.transform -- normalize product SKUs to uppercase
transform_step = S.transform("sku", str.upper)
assert callable(transform_step)

# S.guard -- assert critical invariants before charging the card
guard_step = S.guard(lambda s: "payment_method" in s, "Payment method required before checkout")
assert callable(guard_step)

# S.log -- debug-print key order fields during development
log_step = S.log("order_id", "total")
assert callable(log_step)

# S.compute -- derive shipping cost from order weight and destination
compute_step = S.compute(shipping_cost=lambda s: s.get("weight_kg", 0) * s.get("rate_per_kg", 5.0))
assert callable(compute_step)

# --- 6. Full e-commerce pipeline: all primitives in one expression ---

ecommerce_pipeline = (
    # Set default values for the order
    S.default(currency="USD", shipping_method="standard")
    # Parse and classify the incoming order
    >> Agent("order_classifier", MODEL).instruct("Classify the order type.").outputs("order_type")
    # Route to the appropriate fulfillment handler
    >> Route("order_type")
    .eq("digital", Agent("digital_delivery", MODEL).instruct("Deliver digital product.").outputs("delivery_status"))
    .eq("physical", Agent("warehouse_pick", MODEL).instruct("Pick and pack from warehouse.").outputs("delivery_status"))
    .otherwise(Agent("custom_handler", MODEL).instruct("Handle custom order.").outputs("delivery_status"))
    # Observe the routing result for analytics
    >> tap(lambda s: None)  # no-op observation point
    # Assert contract: routing must produce a delivery status
    >> expect(lambda s: "delivery_status" in s, "Fulfillment must set delivery_status")
    # Compute estimated delivery date
    >> S.compute(eta_days=lambda s: 1 if s.get("order_type") == "digital" else 5)
    # Send confirmation to customer
    >> Agent("notification_sender", MODEL).instruct("Send order confirmation email.").outputs("confirmation_id")
)

assert isinstance(ecommerce_pipeline, Pipeline)
built_full = ecommerce_pipeline.build()
# S.default, order_classifier, route_agent, tap, expect, compute, notification_sender = 7 steps
assert len(built_full.sub_agents) == 7

# --- 7. sub_agent() -- order coordinator with specialized workers ---

order_coordinator = (
    Agent("order_coordinator", MODEL)
    .instruct("Coordinate order processing across fulfillment centers.")
    .sub_agent(Agent("east_warehouse", MODEL).instruct("Handle East Coast fulfillment."))
    .sub_agent(Agent("west_warehouse", MODEL).instruct("Handle West Coast fulfillment."))
)
built_coord = order_coordinator.build()
assert len(built_coord.sub_agents) == 2

# --- 8. include_history() -- stateless payment processor ---

stateless_processor = (
    Agent("payment_gateway", MODEL).include_history("none").instruct("Process payment using only state data.")
)
assert stateless_processor._config["include_contents"] == "none"

# .history() still works as short alias
short_alias = Agent("gateway", MODEL).history("none").instruct("Process payment.")
assert short_alias._config["include_contents"] == "none"
```
:::
::::

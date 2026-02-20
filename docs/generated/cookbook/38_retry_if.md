# Retry If: API Integration Agent That Retries on Transient Failures

*How to use retry if: api integration agent that retries on transient failures with the fluent API.*

_Source: `38_retry_if.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK has no built-in conditional retry. You'd need to:
#   1. Wrap the agent in a LoopAgent
#   2. Create a custom checkpoint BaseAgent that evaluates a predicate
#   3. Yield Event(actions=EventActions(escalate=True)) to exit when satisfied
# For a payment gateway integration, this means 30+ lines of boilerplate
# just to handle transient 503 errors.
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Loop

# Scenario: A payment processing agent that calls an external gateway.
# Transient failures (timeouts, rate limits) should trigger automatic retries,
# but permanent failures (invalid card) should stop immediately.

# .retry_if(): keep retrying while the predicate returns True
payment_processor = (
    Agent("payment_processor")
    .model("gemini-2.5-flash")
    .instruct(
        "Process the payment through the gateway. Report status as 'success', 'transient_error', or 'permanent_error'."
    )
    .outputs("payment_status")
    .retry_if(lambda s: s.get("payment_status") == "transient_error", max_retries=3)
)

# retry_if on a pipeline -- retry the entire charge-then-verify flow
charge_and_verify = (
    Agent("charge_agent")
    .model("gemini-2.5-flash")
    .instruct("Submit charge to payment gateway.")
    .outputs("charge_result")
    >> Agent("verification_agent")
    .model("gemini-2.5-flash")
    .instruct("Verify the charge was recorded by the bank.")
    .outputs("verified")
).retry_if(lambda s: s.get("verified") != "confirmed", max_retries=5)

# Equivalence: retry_if(p) == loop_until(not p)
# These produce identical behavior for an inventory sync agent:
via_retry = (
    Agent("inventory_sync")
    .model("gemini-2.5-flash")
    .retry_if(lambda s: s.get("sync_status") != "complete", max_retries=4)
)
via_loop = (
    Agent("inventory_sync")
    .model("gemini-2.5-flash")
    .loop_until(lambda s: s.get("sync_status") == "complete", max_iterations=4)
)
```
:::
::::

## Equivalence

```python
from adk_fluent.workflow import Loop as LoopBuilder

# retry_if creates a Loop builder
assert isinstance(payment_processor, LoopBuilder)

# max_retries maps to max_iterations
assert payment_processor._config["max_iterations"] == 3

# Pipeline retry also creates a Loop
assert isinstance(charge_and_verify, LoopBuilder)
assert charge_and_verify._config["max_iterations"] == 5

# The predicate is inverted: retry_if(p) stores not-p as until_predicate
until_pred = payment_processor._config["_until_predicate"]
assert until_pred({"payment_status": "success"}) is True  # exit: stop retrying
assert until_pred({"payment_status": "transient_error"}) is False  # continue retrying

# Both retry_if and loop_until produce Loop builders with identical structure
assert isinstance(via_retry, LoopBuilder)
assert isinstance(via_loop, LoopBuilder)
assert via_retry._config["max_iterations"] == via_loop._config["max_iterations"]

# Build verifies checkpoint agent is injected
built = payment_processor.build()
assert len(built.sub_agents) >= 2
assert built.sub_agents[-1].name == "_until_check"
```

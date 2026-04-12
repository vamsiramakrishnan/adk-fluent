"""
Retry If: API Integration Agent That Retries on Transient Failures

Converted from cookbook example: 38_loop_while.py

Usage:
    cd examples
    adk web loop_while
"""

from adk_fluent import Agent, Loop
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Scenario: A payment processing agent that calls an external gateway.
# Transient failures (timeouts, rate limits) should trigger automatic retries,
# but permanent failures (invalid card) should stop immediately.

# .loop_while(): keep retrying while the predicate returns True
payment_processor = (
    Agent("payment_processor")
    .model("gemini-2.5-flash")
    .instruct(
        "Process the payment through the gateway. Report status as 'success', 'transient_error', or 'permanent_error'."
    )
    .writes("payment_status")
    .loop_while(lambda s: s.get("payment_status") == "transient_error", max_iterations=3)
)

# loop_while on a pipeline -- retry the entire charge-then-verify flow
charge_and_verify = (
    Agent("charge_agent")
    .model("gemini-2.5-flash")
    .instruct("Submit charge to payment gateway.")
    .writes("charge_result")
    >> Agent("verification_agent")
    .model("gemini-2.5-flash")
    .instruct("Verify the charge was recorded by the bank.")
    .writes("verified")
).loop_while(lambda s: s.get("verified") != "confirmed", max_iterations=5)

# Equivalence: loop_while(p) == loop_until(not p)
# These produce identical behavior for an inventory sync agent:
via_retry = (
    Agent("inventory_sync")
    .model("gemini-2.5-flash")
    .loop_while(lambda s: s.get("sync_status") != "complete", max_iterations=4)
)
via_loop = (
    Agent("inventory_sync")
    .model("gemini-2.5-flash")
    .loop_until(lambda s: s.get("sync_status") == "complete", max_iterations=4)
)

root_agent = via_loop.build()

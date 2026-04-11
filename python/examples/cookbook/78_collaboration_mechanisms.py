"""Agent Collaboration Mechanisms — Six Ways Agents Work Together

Demonstrates all six collaboration primitives in adk-fluent:

1. Transfer — Agent A hands off to Agent B (LLM-routed or deterministic)
2. Tool-call — Agent A calls Agent B as a function, stays in control
3. Shared state — Agents read/write a common key-value store
4. Interrupt — External signals stop or reroute a running agent
5. Notify — Fire-and-forget: send without waiting
6. Observe — Watch agent output and react to state changes

Each pattern maps to a real-world collaboration analogy:
  Transfer = handing off a customer to another department
  Tool-call = asking a colleague a question and waiting for the answer
  Shared state = whiteboard in a shared office
  Interrupt = tapping someone on the shoulder while they're working
  Notify = sending a Slack message
  Observe = monitoring a live dashboard
"""

from adk_fluent import Agent, Pipeline, Route

# ======================================================================
# 1. TRANSFER — Agent A stops, Agent B starts
# ======================================================================

# 1a. LLM-routed transfer: coordinator decides who to hand off to
coordinator = (
    Agent("support_router", "gemini-2.5-flash")
    .instruct("Route the customer to the right specialist.")
    .sub_agent(
        Agent("billing", "gemini-2.5-flash")
        .instruct("Handle billing and payment questions.")
        .describe("Billing specialist — payments, invoices, refunds")
        .isolate()  # Completes task, auto-returns to parent
    )
    .sub_agent(
        Agent("technical", "gemini-2.5-flash")
        .instruct("Handle technical troubleshooting.")
        .describe("Technical specialist — bugs, errors, setup issues")
        .isolate()
    )
)

# 1b. Deterministic routing: no LLM decision needed
router = (
    Route("department")
    .eq("billing", Agent("billing_handler").instruct("Handle billing."))
    .eq("technical", Agent("tech_handler").instruct("Handle tech."))
    .otherwise(Agent("general_handler").instruct("Handle general queries."))
)

# --- ASSERT ---
built_coordinator = coordinator.build()
assert len(built_coordinator.sub_agents) == 2
assert built_coordinator.sub_agents[0].name == "billing"
assert built_coordinator.sub_agents[1].name == "technical"
assert built_coordinator.sub_agents[0].disallow_transfer_to_parent is True

built_router = router.build()
assert built_router.name == "route_department"

# ======================================================================
# 2. TOOL-CALL — Agent A calls Agent B, stays in control
# ======================================================================

researcher = Agent("fact_checker", "gemini-2.5-flash").instruct(
    "Check facts. Return verified information with sources."
)

analyst = (
    Agent("analyst", "gemini-2.5-flash")
    .instruct("Analyze the user's question. Use fact_checker for verification.")
    .agent_tool(researcher)  # Analyst stays in control
)

# --- ASSERT ---
built_analyst = analyst.build()
# agent_tool adds to tools, not sub_agents
assert len(built_analyst.tools) > 0

# ======================================================================
# 3. SHARED STATE — Whiteboard pattern
# ======================================================================

pipeline = (
    Agent("researcher", "gemini-2.5-flash").instruct("Research {topic}. Be thorough.").writes("findings")
    >> Agent("writer", "gemini-2.5-flash")
    .reads("findings")
    .instruct("Write a summary based on: {findings}")
    .writes("draft")
    >> Agent("reviewer", "gemini-2.5-flash")
    .reads("findings", "draft")
    .instruct("Review the draft against the original findings.")
    .writes("verdict")
)

# --- ASSERT ---
built_pipeline = pipeline.build()
assert len(built_pipeline.sub_agents) == 3
assert built_pipeline.sub_agents[0].name == "researcher"

# ======================================================================
# 4. INTERRUPT — Stop or reroute a running agent
# ======================================================================

from adk_fluent import G

# 4a. Timeout interrupt
slow_agent = Agent("deep_thinker", "gemini-2.5-flash").instruct("Analyze in extreme detail.").timeout(30)

# 4b. Guard interrupt (block bad output)
guarded_agent = Agent("writer", "gemini-2.5-flash").instruct("Write a customer response.").guard(G.length(max=500))


# 4c. Before-model interrupt (budget gate)
def budget_gate(callback_context, llm_request):
    tokens_used = callback_context.state.get("total_tokens", 0)
    if tokens_used > 50000:
        return {"role": "model", "parts": [{"text": "Budget exceeded."}]}
    return None


budget_agent = Agent("worker", "gemini-2.5-flash").instruct("Do the work.").before_model(budget_gate)

# 4d. Human-in-the-loop gate
from adk_fluent import gate

gated_pipeline = (
    Agent("drafter", "gemini-2.5-flash").instruct("Draft a response.").writes("draft")
    >> gate(lambda s: s.get("risk") == "high", message="Approve high-risk action?")
    >> Agent("sender", "gemini-2.5-flash").reads("draft").instruct("Send the approved draft.")
)

# 4e. Fallback on failure
safe_agent = Agent("fast", "gemini-2.5-flash").instruct("Quick answer.") // Agent("strong", "gemini-2.5-pro").instruct(
    "Thorough answer."
)

# --- ASSERT ---
from adk_fluent._primitive_builders import TimedAgent, _GateBuilder

assert isinstance(slow_agent, TimedAgent)
assert isinstance(gated_pipeline, Pipeline)

# ======================================================================
# 5. NOTIFY — Fire-and-forget
# ======================================================================

from adk_fluent import notify, dispatch, join

# 5a. notify() — simplified fire-and-forget
audit_logger = Agent("audit", "gemini-2.5-flash").instruct("Log this interaction.")
email_sender = Agent("emailer", "gemini-2.5-flash").instruct("Send confirmation email.")

notify_pipeline = (
    Agent("worker", "gemini-2.5-flash").instruct("Handle the customer request.").writes("result")
    >> notify(audit_logger, email_sender)  # Fire both, don't wait
    >> Agent("formatter", "gemini-2.5-flash").reads("result").instruct("Format the result.")
)

# 5b. dispatch() + join() — fire and collect later
dispatch_pipeline = (
    Agent("worker", "gemini-2.5-flash").instruct("Do work.").writes("result")
    >> dispatch(audit_logger, email_sender)  # Fire in background
    >> Agent("formatter", "gemini-2.5-flash").instruct("Format.")  # Continue immediately
    >> join()  # Wait for background tasks here
)

# --- ASSERT ---
from adk_fluent._primitive_builders import _NotifyBuilder

notify_step = notify(audit_logger, email_sender)
assert isinstance(notify_step, _NotifyBuilder)
built_notify = notify_step.build()
assert len(built_notify.sub_agents) == 2

# ======================================================================
# 6. OBSERVE — Watch agent output, react to state changes
# ======================================================================

from adk_fluent import tap, watch

# 6a. tap() — passive observation (no state mutation)
observed_pipeline = (
    Agent("researcher", "gemini-2.5-flash").instruct("Research.").writes("findings")
    >> tap(lambda s: print(f"Research done: {len(s.get('findings', ''))} chars"))
    >> Agent("writer", "gemini-2.5-flash").reads("findings").instruct("Write.")
)

# 6b. watch() — reactive state trigger
notifier = Agent("slack_notifier", "gemini-2.5-flash").instruct("Notify team about draft.")

reactive_pipeline = (
    Agent("writer", "gemini-2.5-flash").instruct("Write a draft.").writes("draft")
    >> watch("draft", notifier)  # When draft changes, trigger notifier
    >> Agent("reviewer", "gemini-2.5-flash").reads("draft").instruct("Review the draft.")
)

# 6c. watch() with a function handler
watch_fn_pipeline = (
    Agent("scorer", "gemini-2.5-flash").instruct("Score the submission.").writes("score")
    >> watch("score", lambda old, new, state: {"score_changed": True})
    >> Agent("reporter", "gemini-2.5-flash").instruct("Report results.")
)

# --- ASSERT ---
from adk_fluent._primitive_builders import _WatchBuilder

w = watch("draft", notifier)
assert isinstance(w, _WatchBuilder)
built_watch = w.build()
assert built_watch.name.startswith("watch_draft_")

# ======================================================================
# BONUS: group_chat() — round-robin multi-agent discussion
# ======================================================================

from adk_fluent.patterns import group_chat

discussion = group_chat(
    Agent("researcher", "gemini-2.5-flash").instruct("Provide research and facts."),
    Agent("writer", "gemini-2.5-flash").instruct("Draft based on the discussion."),
    Agent("critic", "gemini-2.5-flash").instruct("Critique. Set done=true when satisfied."),
    max_rounds=3,
    stop_key="done",
)

# --- ASSERT ---
from adk_fluent import Loop

assert isinstance(discussion, Loop)
built_discussion = discussion.build()
# Loop flattens: 3 agents + 1 _CheckpointAgent (until predicate)
assert len(built_discussion.sub_agents) == 4
agent_names = [a.name for a in built_discussion.sub_agents[:3]]
assert agent_names == ["researcher", "writer", "critic"]

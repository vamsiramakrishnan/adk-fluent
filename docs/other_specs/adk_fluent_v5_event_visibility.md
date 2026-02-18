# Event Visibility in Composed Pipelines: A Mechanism, Not a Patch

## The Problem, Precisely Stated

In a composed agent DAG like `classifier >> Route("intent").eq("booking", booker)`, every 
LLM agent produces events that flow through a single channel to the client. ADK's 
`SequentialAgent._run_async_impl` does a bare `yield event` for every sub-agent event. 
There is no concept of "this event is for the next agent" vs "this event is for the user."

The result: intermediate agents' outputs — classification labels, JSON blobs, confidence 
scores, draft text — appear as chat messages alongside the actual user-facing response.

This isn't a bug. It's an architecture designed for single-agent systems extended to 
multi-agent composition without adding a visibility layer.

---

## What ADK Already Gives Us

Reading the Events documentation and the actual source code reveals that ADK already has 
most of the machinery. We don't need to fight the framework — we need to use it.

### 1. Events ARE Recorded Regardless

The Runner's `_exec_with_plugin` method processes events in this order:

```python
# From Runner._exec_with_plugin (actual source)
async for event in agen:
    _apply_run_config_custom_metadata(event, invocation_context.run_config)
    
    # STEP 1: Event is persisted to session history
    if self._should_append_event(event, is_live_call):
        await self.session_service.append_event(session=session, event=event)
    
    # STEP 2: Plugin gets to modify the event
    modified_event = await plugin_manager.run_on_event_callback(
        invocation_context=invocation_context, event=event
    )
    
    # STEP 3: Modified or original event is yielded to client
    if modified_event:
        yield modified_event
    else:
        yield event
```

**This means**: Every event is recorded in `session.events` BEFORE the plugin touches it. 
The plugin can modify what the client sees WITHOUT affecting the historical record. This 
is exactly the separation we need: full history for debugging/audit, filtered stream for 
the user.

### 2. `custom_metadata` Is a First-Class Event Field

```python
# From Event model fields (actual source)
custom_metadata: Optional[dict[str, Any]] = None
```

ADK already merges RunConfig's `custom_metadata` into every event:

```python
def _apply_run_config_custom_metadata(event, run_config):
    if not run_config or not run_config.custom_metadata:
        return
    event.custom_metadata = {
        **run_config.custom_metadata,
        **(event.custom_metadata or {}),
    }
```

This is the annotation channel. No invention required.

### 3. `on_event_callback` Is the Interception Point

```python
class BasePlugin(ABC):
    async def on_event_callback(
        self, *, invocation_context: InvocationContext, event: Event
    ) -> Optional[Event]:
        """Callback executed after an event is yielded from runner.
        
        Returns:
            A non-None return may be used by the framework to modify or 
            replace the response. Returning None allows the original 
            response to be used.
        """
        pass
```

A plugin can inspect every event, annotate it, modify it, or replace it. This runs 
after persistence, before the client.

### 4. `event.author` Carries Agent Identity

Every event has an `author` field — the name of the agent that produced it. Combined 
with the topology (which we know from the IR), we know whether that agent is a terminal 
node or an intermediate one.

### 5. `is_final_response()` Is the Client-Side Filter

```python
def is_final_response(self) -> bool:
    if self.actions.skip_summarization or self.long_running_tool_ids:
        return True
    return (
        not self.get_function_calls()
        and not self.get_function_responses()
        and not self.partial
        and not self.has_trailing_code_execution_result()
    )
```

This returns True for ANY text content event — including intermediate agents. There's 
no topology awareness. This is the filter most clients use. And it's the source of the 
"leaking intermediate messages" problem.

---

## The Mechanism: Topology-Inferred Event Visibility

### Core Principle

**In a DAG, the system can INFER which agents are user-facing from the topology.** 

A node is "terminal" (user-facing) if:
- It has no successors in the sequence (last step in a pipeline)
- It's the final branch target in a Route (the response agent, not the classifier)
- It's explicitly marked as user-facing by the developer

A node is "intermediate" (internal) if:
- It has successors (not the last step)
- It's a zero-cost node (transform, tap, route, checkpoint)
- It's explicitly marked as internal by the developer

The system should default to **inferring** visibility from topology, and allow the 
developer to **override** when inference is wrong.

### When Inference Is Right (Most Cases)

```python
# classifier is intermediate (has successor: Route)
# booker is terminal (no successor in its branch)
# info_agent is terminal (no successor in its branch)
classifier >> Route("intent").eq("booking", booker).eq("info", info_agent)
```

Inference: classifier = internal, booker = user-facing, info_agent = user-facing. ✅

```python
# fetcher is intermediate, summarizer is terminal
fetcher >> summarizer
```

Inference: fetcher = internal, summarizer = user-facing. ✅

```python
# All intermediate except synthesizer
map_over("docs", summarizer) >> synthesizer
```

Inference: summarizer (inside map_over) = internal, synthesizer = user-facing. ✅

```python
# scorer is intermediate, both response agents are terminal
scorer >> Route("score").gt(0.8, confident).otherwise(cautious)
```

Inference: scorer = internal, confident = user-facing, cautious = user-facing. ✅

### When Inference Is Wrong (Override Needed)

```python
# Human review pipeline: ALL steps should be visible
drafter >> reviewer >> editor
```

Inference says: drafter = internal, reviewer = internal, editor = user-facing.
But the user WANTS to see drafter and reviewer outputs for review.
Override: mark all as user-facing, or mark pipeline as "transparent."

```python
# Progressive UX: show thinking steps
analyzer >> researcher >> synthesizer
```

Inference says only synthesizer is visible. But UX wants to show each step with 
"Analyzing..." → "Researching..." → final answer.
Override: mark all as user-facing, or use a "progressive" visibility mode.

```python
# Single agent with no composition — everything visible
agent = Agent("helper").instruct("...")
```

No composition, no inference. Everything visible. Same as ADK today.

---

## Implementation: Three Layers

### Layer 1: IR Topology Analysis (Build Time)

The IR already knows the DAG structure. Add a function that walks the graph and 
classifies each node:

```python
def infer_visibility(ir_root) -> dict[str, Literal["user", "internal", "zero_cost"]]:
    """Walk the IR and infer which nodes are user-facing vs internal.
    
    Rules:
    1. Terminal nodes in any branch are "user" (they're the last to speak)
    2. Non-terminal nodes with successors are "internal" 
    3. Zero-cost nodes (Transform, Tap, Route, Checkpoint) are always "zero_cost"
    4. Explicit developer annotations override inference
    """
    visibility = {}
    
    def _walk(node, has_successor: bool):
        # Zero-cost nodes are never user-facing
        if isinstance(node, (TransformNode, TapNode, RouteNode, CheckpointNode)):
            visibility[node.name] = "zero_cost"
            # But recurse into Route branches
            if isinstance(node, RouteNode):
                for _, branch in node.rules:
                    _walk(branch, has_successor=False)  # Branch targets are terminal
                if node.default:
                    _walk(node.default, has_successor=False)
            return
        
        # Check for explicit developer override
        if hasattr(node, 'visibility') and node.visibility is not None:
            visibility[node.name] = node.visibility
            return
        
        # Sequence: only last child is terminal
        if isinstance(node, SequenceNode):
            for i, child in enumerate(node.children):
                is_last = (i == len(node.children) - 1)
                _walk(child, has_successor=not is_last or has_successor)
            return
        
        # Parallel: all children are terminal (all speak to user)
        if isinstance(node, ParallelNode):
            for child in node.children:
                _walk(child, has_successor=has_successor)
            return
        
        # Loop body: internal (user sees the loop result, not each iteration)
        if isinstance(node, LoopNode):
            _walk(node.body, has_successor=True)  # Body is always intermediate
            return
        
        # MapOver body: internal (user sees the aggregated result)
        if isinstance(node, MapOverNode):
            _walk(node.body, has_successor=True)
            return
        
        # Fallback children: only the successful one is visible
        # But we can't know which at build time — mark all as user-facing
        if isinstance(node, FallbackNode):
            for child in node.children:
                _walk(child, has_successor=has_successor)
            return
        
        # Leaf agent node
        if has_successor:
            visibility[node.name] = "internal"
        else:
            visibility[node.name] = "user"
    
    _walk(ir_root, has_successor=False)
    return visibility
```

This produces a map like:
```python
{
    "classifier": "internal",
    "route_intent": "zero_cost",
    "booker": "user",
    "info_agent": "user",
}
```

### Layer 2: Event Annotation Plugin (Runtime)

A plugin that uses the visibility map to annotate events as they flow through:

```python
class VisibilityPlugin(BasePlugin):
    """Annotates events with topology-inferred visibility.
    
    Events are ALWAYS recorded in session history (that happens before this 
    plugin runs). This plugin annotates events with visibility metadata so 
    clients can filter appropriately.
    
    In 'annotate' mode: adds metadata, yields all events (client filters)
    In 'filter' mode: suppresses content of internal events (only state flows)
    """
    
    def __init__(
        self,
        visibility_map: dict[str, str],
        mode: Literal["annotate", "filter"] = "annotate",
    ):
        super().__init__(name="adk_fluent_visibility")
        self._visibility = visibility_map
        self._mode = mode
    
    async def on_event_callback(
        self, *, invocation_context: InvocationContext, event: Event
    ) -> Optional[Event]:
        # Determine this event's visibility
        author = event.author
        vis = self._visibility.get(author, "user")  # Default: user-facing
        
        # Always annotate
        event.custom_metadata = event.custom_metadata or {}
        event.custom_metadata["adk_fluent.visibility"] = vis
        event.custom_metadata["adk_fluent.is_user_facing"] = (vis == "user")
        
        if self._mode == "annotate":
            # Client decides what to show
            return event
        
        elif self._mode == "filter":
            # Suppress content of internal/zero_cost events
            if vis != "user" and self._is_user_facing_content(event):
                return self._strip_content(event)
            return event
    
    def _is_user_facing_content(self, event: Event) -> bool:
        """Is this the kind of event that would show as a chat message?"""
        if not event.content or not event.content.parts:
            return False
        if event.get_function_calls() or event.get_function_responses():
            return False  # Tool traffic, not chat
        if event.partial:
            return False  # Streaming chunk
        if event.actions and (event.actions.transfer_to_agent or event.actions.escalate):
            return False  # Control flow
        return True  # Text content — this would show in chat
    
    def _strip_content(self, event: Event) -> Event:
        """Remove content but preserve state_delta and control signals."""
        from google.adk.events.event import Event as ADKEvent
        from google.adk.events.event_actions import EventActions
        
        # If there's state_delta to preserve, emit a content-less event
        if event.actions and (event.actions.state_delta or event.actions.artifact_delta):
            return ADKEvent(
                invocation_id=event.invocation_id,
                author=event.author,
                branch=event.branch,
                actions=event.actions,
                custom_metadata=event.custom_metadata,
                timestamp=event.timestamp,
            )
        
        # No state to preserve — return None to use original? No.
        # Return a minimal event so session history isn't disrupted
        return ADKEvent(
            invocation_id=event.invocation_id,
            author=event.author,
            branch=event.branch,
            actions=EventActions(state_delta={}, artifact_delta={}),
            custom_metadata=event.custom_metadata,
            timestamp=event.timestamp,
        )
```

### Layer 3: Developer Controls (Builder API)

Three levels of control, from least effort to most explicit:

**Level 0: Automatic (default when using Pipeline)**

```python
# Just works. Classifier is inferred as internal from topology.
pipeline = classifier >> Route("intent").eq("booking", booker)
root_agent = pipeline.build()  # Visibility inferred, plugin attached
```

The `Pipeline.build()` method:
1. Calls `to_ir()` to get the DAG
2. Runs `infer_visibility()` on the IR
3. Creates `VisibilityPlugin(visibility_map, mode="annotate")`
4. Attaches the plugin to the resulting agent (via Runner plugins)

**Level 1: Per-agent override**

```python
# Force an intermediate agent to be visible (progressive UX)
analyzer = Agent("analyzer").instruct("...").show()    # Override: user-facing

# Force a terminal agent to be hidden (utility agent at end of branch)
logger = Agent("logger").instruct("...").hide()        # Override: internal

pipeline = analyzer >> researcher >> synthesizer
```

`.show()` and `.hide()` set `visibility` on the builder, which propagates to the IR 
node. `infer_visibility()` respects explicit annotations over inference.

**Level 2: Pipeline-level policy**

```python
# All events visible (debugging, human-in-the-loop review)
pipeline = (drafter >> reviewer >> editor).transparent()

# Only terminal events visible (production, clean UX) — this is the default
pipeline = (classifier >> booker).filtered()

# Annotate-only (client decides, all events flow, metadata present)
pipeline = (classifier >> booker).annotated()
```

These set the mode on the pipeline, controlling whether the plugin annotates or filters.

**Level 3: Client-side filtering (works with all modes)**

```python
# The "annotate" mode puts metadata on every event. Client filters:
async for event in runner.run_async(...):
    meta = event.custom_metadata or {}
    
    # Option A: Only show user-facing events
    if meta.get("adk_fluent.is_user_facing", True) and event.is_final_response():
        show_to_user(event)
    
    # Option B: Show everything but style internal events differently
    if event.is_final_response():
        if meta.get("adk_fluent.visibility") == "internal":
            show_as_thinking_step(event)  # Gray, collapsed, "thinking..."
        else:
            show_as_response(event)       # Normal chat message
```

---

## How This Composes with ADK's Existing Mechanisms

### With `output_key`

`output_key` writes LLM output to state AND yields the event. With visibility:
- Internal agent with `output_key`: state write happens, content suppressed. ✅
- Internal agent WITHOUT `output_key`: content suppressed, output lost. Contract 
  checker warns: "Agent 'classifier' is internal but has no output_key. Its LLM 
  output will be suppressed and not saved to state."

### With `is_final_response()`

`is_final_response()` doesn't change. The visibility layer works at a different level:
- `is_final_response()` answers: "Is this a complete text message?" (vs tool call, 
  partial stream, etc.)
- Visibility answers: "Should this complete text message be shown to the user?"

A client combining both:
```python
if event.is_final_response():
    if (event.custom_metadata or {}).get("adk_fluent.is_user_facing", True):
        show_to_user(event)
```

### With `adk web`

adk web shows ALL events in its Events tab — this is the debugging view. Since 
events are recorded in session history BEFORE the plugin modifies them, adk web 
always has the full picture.

In "filter" mode, the chat view in adk web would show only user-facing events. 
In "annotate" mode, adk web could be extended to show internal events differently 
(grayed out, collapsed). Even without adk web changes, the Events tab always shows 
everything.

### With OTel / Telemetry

Every event still generates OTel spans (the `tracer.start_as_current_span('invoke_agent')` 
wraps all of `run_async`). Visibility doesn't affect telemetry. You always see the full 
trace. The visibility metadata could be added as a span attribute for correlation:

```
adk_fluent.visibility = "internal"
adk_fluent.is_user_facing = false
```

### With Session History and Replay

Session history is complete. If you replay the session, you see all events including 
internal ones. The visibility annotation is in `custom_metadata`, so replay tools can 
reconstruct the filtered view.

### With Callbacks

ADK callbacks (`before_agent`, `after_agent`, etc.) fire for ALL agents, including 
internal ones. Visibility doesn't suppress callback execution — it only affects what 
the client stream shows. If you have a `before_agent_callback` on an internal agent, 
it still runs.

---

## Scenarios Walked Through

### Scenario 1: Classification → Routing (Most Common)

```python
classifier = (Agent("classifier")
    .instruct("Output one word: booking, info, or complaint")
    .output_key("intent"))

booker = Agent("booker").instruct("Help book a flight based on intent: {intent}")
info = Agent("info").instruct("Provide information")

pipeline = classifier >> Route("intent").eq("booking", booker).eq("info", info)
```

**Inferred visibility**: classifier=internal, route_intent=zero_cost, booker=user, info=user

**Event flow** (user says "I want to fly to London"):

| # | Author | Content | Visibility | Client Sees? |
|---|--------|---------|-----------|-------------|
| 1 | user | "I want to fly to London" | — | ✅ (user input) |
| 2 | classifier | "booking" | internal | ❌ (suppressed/annotated) |
| 3 | route_intent | — (state only) | zero_cost | ❌ (no content) |
| 4 | booker | "I'd be happy to help you book a flight to London! What dates?" | user | ✅ |

Session history has all 4 events. Client sees events 1 and 4.

### Scenario 2: Iterative Refinement Loop

```python
drafter = Agent("drafter").instruct("Write a draft").output_key("draft")
reviewer = Agent("reviewer").instruct("Review the draft: {draft}").output_key("feedback")
refiner = Agent("refiner").instruct("Refine based on: {feedback}").output_key("draft")

pipeline = drafter >> loop_until(
    lambda s: s.get("feedback", "").startswith("APPROVED"),
    reviewer >> refiner
)
```

**Inferred visibility**: drafter=internal (has successor: loop), reviewer=internal (inside 
loop body), refiner=internal (inside loop body, not last in outer pipeline... but the 
loop IS the last step).

**Problem**: Who speaks to the user? The refined draft after the loop exits. But the 
loop body's last agent (refiner) writes to state, it doesn't "present" a final answer.

**Solution**: Add a presenter agent, or override:

```python
# Option A: Add explicit final step
pipeline = drafter >> loop_until(..., reviewer >> refiner) >> presenter

# Option B: Override the loop to be transparent
pipeline = drafter >> loop_until(..., reviewer >> refiner).show()
```

### Scenario 3: Progressive UX ("Thinking Steps")

```python
analyzer = Agent("analyzer").instruct("Analyze the query").show()     # Override
researcher = Agent("researcher").instruct("Research findings").show()  # Override  
synthesizer = Agent("synthesizer").instruct("Synthesize final answer")

pipeline = analyzer >> researcher >> synthesizer
```

**Visibility**: analyzer=user (overridden), researcher=user (overridden), synthesizer=user (inferred)

Client sees all three, can render as progressive steps.

### Scenario 4: MapOver with Synthesis

```python
summarizer = Agent("summarizer").instruct("Summarize this document: {item}")
synthesizer = Agent("synthesizer").instruct("Synthesize all summaries: {results}")

pipeline = map_over("documents", summarizer, output_key="results") >> synthesizer
```

**Inferred visibility**: summarizer=internal (inside map_over body), synthesizer=user (terminal)

Client sees only the synthesis. Session history has all 10 individual summaries.

### Scenario 5: Human-in-the-Loop Review

```python
pipeline = (drafter >> reviewer >> editor).transparent()
```

**Visibility**: All three = user (transparent overrides all inference)

Client sees all outputs. User can review each step.

### Scenario 6: Single Agent (No Composition)

```python
agent = Agent("helper").instruct("Help the user").build()
runner = Runner(agent=agent, ...)
```

No pipeline, no IR, no visibility plugin. All events visible. **Exactly like ADK today.** 
Zero behavioral change for non-fluent users.

---

## The Inference Rules, Formally

```
VISIBILITY(node, has_successor) =
  | node.visibility != None  → node.visibility        // Developer override
  | node ∈ {Transform, Tap, Route, Checkpoint}  → "zero_cost"
  | node is Sequence([c₁...cₙ])  → 
      VISIBILITY(cᵢ, True) for i < n
      VISIBILITY(cₙ, has_successor)
  | node is Parallel([c₁...cₙ])  →
      VISIBILITY(cᵢ, has_successor) for all i
  | node is Loop(body)  → VISIBILITY(body, True)       // Loop body is internal
  | node is MapOver(body)  → VISIBILITY(body, True)    // Map body is internal
  | node is Route(rules, default)  →
      VISIBILITY(branch, False) for each branch        // Branch targets are terminal
  | node is Fallback([c₁...cₙ])  →
      VISIBILITY(cᵢ, has_successor) for all i          // Any might win
  | has_successor  → "internal"
  | ¬has_successor  → "user"
```

The key insight: **"has_successor" propagates downward through the graph.** A node is 
internal not because of what IT is, but because of where it SITS in the topology.

---

## What This Means for adk-fluent

### It's Not a Wrapper Feature — It's a Composition Feature

A wrapper library (`.instruct()` instead of `instruction=`) can't do this. You need:
1. The **IR** to know the DAG topology
2. The **inference function** to classify nodes from topology
3. The **plugin** to annotate/filter events at runtime
4. The **builder API** to accept overrides

These are all hand-written composition infrastructure — exactly the value proposition 
of adk-fluent beyond being a fluent API.

### It Uses ADK's Own Mechanisms

No monkey-patching. No custom runtime. No event suppression hacks.
- `custom_metadata` is a first-class Event field
- `on_event_callback` is a first-class Plugin method
- `session.events` records everything before the plugin runs
- `RunConfig.custom_metadata` provides run-level metadata

We're using ADK exactly as designed, applying composition knowledge that ADK doesn't 
have because ADK doesn't have an IR.

### Default Behavior Changes

| Scenario | ADK Today | adk-fluent (annotate mode) | adk-fluent (filter mode) |
|----------|-----------|---------------------------|--------------------------|
| Single agent | All events visible | Same | Same |
| `a >> b` | Both visible | Both visible, `a` annotated as internal | Only `b` visible |
| `a >> Route >> b/c` | All visible | `a` annotated as internal | Only `b` or `c` visible |
| `map_over(a) >> b` | All visible | `a` iterations annotated as internal | Only `b` visible |
| `loop(a >> b)` | All iterations visible | Iterations annotated as internal | Only post-loop visible |
| `.transparent()` | N/A | All annotated as user | All visible |

**Recommended default**: "annotate" mode. Events flow, metadata present, client decides. 
This is non-breaking — existing code that doesn't check `custom_metadata` sees the same 
behavior as today.

### The Codegen Angle

What should be generated vs hand-written:

**Generated** (from ADK API surface):
- `.show()`, `.hide()` on AgentBuilder — trivial config flags
- `.transparent()`, `.filtered()`, `.annotated()` on Pipeline — config flags

**Hand-written** (composition infrastructure):
- `infer_visibility()` — topology analysis on IR
- `VisibilityPlugin` — event annotation/filtering via ADK plugin protocol
- Integration with `Pipeline.build()` — automatic plugin attachment
- Contract checking — warn on internal agent without `output_key`
- Mermaid rendering — visual distinction for internal vs user-facing nodes

### Lines of Code Estimate

| Component | Lines | Effort |
|-----------|-------|--------|
| `infer_visibility()` on IR | ~80 | Medium (topology recursion) |
| `VisibilityPlugin` | ~60 | Low (uses ADK plugin protocol) |
| Builder API (`.show()`, `.hide()`, etc.) | ~30 | Low (config flags) |
| Pipeline.build() integration | ~20 | Low (attach plugin to Runner) |
| Contract checker integration | ~15 | Low (check internal + no output_key) |
| Mermaid rendering for visibility | ~20 | Low (dashed borders for internal) |
| **Total** | **~225** | **~2 days** |

---

## What This Does NOT Solve

1. **Streaming partial events from internal agents**: If an internal agent streams 
   (partial=True), the filter mode needs to suppress those too. The annotation mode 
   lets the client decide. This is an edge case but a visible one if the client renders 
   streaming text that then "disappears."

2. **Tool calls from internal agents**: An internal classifier might call tools. Those 
   tool call/response events still flow. Should they be suppressed? Probably not — they're 
   infrastructure, not "speech." But the client might render them. The annotation approach 
   lets the client filter appropriately.

3. **Error events from internal agents**: If an internal agent errors, that error should 
   probably bubble up to the user regardless of visibility. The plugin should NOT suppress 
   error events.

4. **Dynamic visibility**: An agent might be internal in one code path and terminal in 
   another (e.g., a Fallback where any child might win). The static inference is 
   conservative here — Fallback children are all marked "user." Runtime awareness would 
   need a different approach.

5. **adk web integration**: adk web doesn't know about `custom_metadata` filtering. 
   In annotate mode, it shows everything (fine for debugging). In filter mode, it would 
   show fewer chat messages. Ideally, adk web would have a toggle: "Show all events / 
   Show user-facing only." This is an adk-web feature request, not an adk-fluent problem.

---

## Summary

| Question | Answer |
|----------|--------|
| Is this inference or annotation? | Both. Infer from topology, annotate on events, let client filter. |
| Does the system record internal events? | Yes. Session history has everything. Plugin runs after persistence. |
| What's the default? | "annotate" mode — non-breaking, client opts into filtering. |
| Can the user override? | Yes. `.show()`, `.hide()`, `.transparent()`, `.filtered()`. |
| Does this need ADK changes? | No. Uses `custom_metadata`, `on_event_callback`, `BasePlugin` — all existing. |
| What does this need from adk-fluent? | IR topology analysis + a plugin + builder flags. ~225 lines. |
| Is this a patch or a mechanism? | Mechanism. Topology inference → event annotation → client filtering. |
| Why can't ADK do this itself? | ADK doesn't have an IR. It doesn't know the DAG topology at runtime. It sees individual agents yielding events, not a composed pipeline with intermediate and terminal nodes. |
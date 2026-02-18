"""Context Engineering with C Transforms"""

# --- NATIVE ---
# Native ADK requires manually setting include_contents and creating
# custom InstructionProvider callables per agent. There is no declarative
# context specification.

# --- FLUENT ---
from adk_fluent import Agent, C

MODEL = "gemini-2.5-flash"

# C.none() — suppress all conversation history
no_ctx = Agent("clean", MODEL).instruct("Process.").context(C.none())

# C.default() — keep default history (explicit pass-through)
default_ctx = Agent("normal", MODEL).instruct("Respond.").context(C.default())

# C.user_only() — only user messages
user_only = Agent("listener", MODEL).instruct("Respond.").context(C.user_only())

# C.from_state() — inject state keys into instruction
from_state = Agent("writer", MODEL).instruct("Write about {topic}.").context(C.from_state("topic"))

# C.window() — last N turn-pairs
windowed = Agent("focused", MODEL).instruct("Analyze.").context(C.window(n=3))

# C.from_agents() — include specific agent outputs
selective = Agent("editor", MODEL).instruct("Edit.").context(C.from_agents("drafter", "reviewer"))

# Composition with +
combined = Agent("analyst", MODEL).instruct("Analyze.").context(
    C.window(n=3) + C.from_state("topic")
)

# Build and verify
built_none = no_ctx.build()
built_default = default_ctx.build()
built_user = user_only.build()
built_state = from_state.build()

# --- ASSERT ---
# C.none() sets include_contents to "none"
assert built_none.include_contents == "none"

# C.default() keeps include_contents as "default"
assert built_default.include_contents == "default"

# C.user_only() sets include_contents to "none" with callable instruction
assert built_user.include_contents == "none"
assert callable(built_user.instruction)

# C.from_state() creates callable instruction provider
assert built_state.include_contents == "none"
assert callable(built_state.instruction)

# Composition stores in config
assert combined._config.get("_context_spec") is not None

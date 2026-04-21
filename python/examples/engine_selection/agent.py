"""
Engine Selection -- Backend-Selectable Agent Execution

The same agent definition can run on different execution backends:
ADK (default), asyncio (zero-dependency), or Temporal (durable).
Use .engine() per-agent or configure() globally. The agent logic
stays identical -- only the execution engine changes.

This is the core concept of the five-layer architecture:
  Definition → Compile → Runtime → Backend → Compute

Converted from cookbook example: 68_engine_selection.py

Usage:
    cd examples
    adk web engine_selection
"""

from adk_fluent import Agent, Pipeline, FanOut, configure, reset_config
from adk_fluent import EngineCapabilities, CompilationResult
from adk_fluent import compile as compile_ir
from adk_fluent.backends import available_backends, get_backend
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# 1. Check what backends are registered
backends = available_backends()

# 2. Per-agent engine selection with .engine()
#    .engine() stores the backend choice; .run.ask() routes accordingly.
agent_adk = Agent("helper").instruct("You help users.").engine("adk")
agent_asyncio = Agent("helper").instruct("You help users.").engine("asyncio")
agent_temporal = Agent("helper").instruct("You help users.").engine("temporal", task_queue="research")

# 3. Global configuration with configure()
#    Sets the default engine for ALL agents that don't specify .engine().
configure(engine="asyncio")
agent_uses_global = Agent("test").instruct("Hello")

# Reset to defaults
reset_config()

# 4. Pipeline with engine selection
#    The engine is set on the outermost builder -- all steps inherit it.
pipeline = (
    Agent("researcher").instruct("Research the topic.")
    >> Agent("writer").instruct("Write the report.")
    >> Agent("reviewer").instruct("Review the report.")
).engine("asyncio")

# 5. Compile IR to different backends explicitly
ir = pipeline.to_ir()
adk_compiled = compile_ir(ir, backend="adk")
asyncio_compiled = compile_ir(ir, backend="asyncio")
temporal_compiled = compile_ir(ir, backend="temporal")

# 6. Inspect capabilities
adk_caps = adk_compiled.capabilities
asyncio_caps = asyncio_compiled.capabilities
temporal_caps = temporal_compiled.capabilities

root_agent = temporal_caps.build()

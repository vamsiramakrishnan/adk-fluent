"""Compute Layer -- Pluggable Model, State, Tool, and Artifact Providers

The compute layer decouples WHERE work runs from HOW it's orchestrated.
Four independent protocols let you swap infrastructure without changing
agent logic:

  ModelProvider   → LLM backend (Gemini, OpenAI, local, mock)
  StateStore      → Session persistence (memory, Redis, SQL)
  ToolRuntime     → Tool execution sandbox
  ArtifactStore   → Binary artifact storage (files, GCS, S3)

Use ComputeConfig to bundle providers, then attach via .compute()
on any builder or configure() globally.
"""

# --- FLUENT ---
from adk_fluent import Agent, Pipeline
from adk_fluent.compute import ComputeConfig
from adk_fluent.compute._protocol import (
    GenerateConfig,
    GenerateResult,
    Message,
    ToolDef,
)
from adk_fluent.compute.memory import (
    InMemoryStateStore,
    InMemoryArtifactStore,
    LocalToolRuntime,
)

# 1. Create infrastructure providers
state_store = InMemoryStateStore()
artifact_store = InMemoryArtifactStore()
tool_runtime = LocalToolRuntime()

# 2. Bundle into ComputeConfig
compute = ComputeConfig(
    model_provider="gemini-2.5-flash",  # Can be a string or ModelProvider instance
    state_store=state_store,
    tool_runtime=tool_runtime,
    artifact_store=artifact_store,
)

# 3. Attach to a builder with .compute()
agent = Agent("analyst").instruct("Analyze the data.").compute(compute).engine("asyncio")

# 4. Or set globally with configure()
from adk_fluent import configure, reset_config

configure(
    engine="asyncio",
    compute=ComputeConfig(state_store=InMemoryStateStore()),
)
# Now all agents without explicit .compute() use the global config
global_agent = Agent("helper").instruct("Help the user.")
reset_config()

# 5. InMemoryStateStore: create, load, save, delete sessions
import asyncio


async def demo_state_store():
    store = InMemoryStateStore()
    session_id = await store.create("my_app", greeting="hello")
    state = await store.load(session_id)
    assert state["greeting"] == "hello"

    await store.save(session_id, {"greeting": "hello", "count": 42})
    state = await store.load(session_id)
    assert state["count"] == 42

    sessions = await store.list_sessions("my_app")
    assert session_id in sessions

    await store.delete(session_id)
    sessions = await store.list_sessions("my_app")
    assert session_id not in sessions


asyncio.run(demo_state_store())

# 6. InMemoryArtifactStore: versioned binary storage


async def demo_artifact_store():
    store = InMemoryArtifactStore()
    v1 = await store.save("report.txt", b"Draft 1")
    await store.save("report.txt", b"Final version")

    # Load latest version
    data = await store.load("report.txt")
    assert data == b"Final version"

    # Load specific version
    data = await store.load("report.txt", version=v1)
    assert data == b"Draft 1"

    # List all versions
    versions = await store.list_versions("report.txt")
    assert len(versions) == 2


asyncio.run(demo_artifact_store())

# 7. LocalToolRuntime: executes tool functions (sync and async)


async def demo_tool_runtime():
    runtime = LocalToolRuntime()

    def add(a: int, b: int) -> int:
        return a + b

    result = await runtime.execute("add", add, {"a": 3, "b": 4})
    assert result == 7


asyncio.run(demo_tool_runtime())

# --- ASSERT ---

# ComputeConfig stores all providers
assert compute.model_provider == "gemini-2.5-flash"
assert compute.state_store is state_store
assert compute.tool_runtime is tool_runtime
assert compute.artifact_store is artifact_store

# Builder stores compute config
assert agent._config["_compute"] is compute
assert agent._config["_engine"] == "asyncio"

# Providers are independent -- swap one without touching others
compute_minimal = ComputeConfig(model_provider="gemini-2.5-pro")
assert compute_minimal.state_store is None
assert compute_minimal.artifact_store is None

# Pipeline can also use .compute()
pipeline = (Agent("a").instruct("Step 1") >> Agent("b").instruct("Step 2")).compute(
    ComputeConfig(state_store=InMemoryStateStore())
)
assert "_compute" in pipeline._config

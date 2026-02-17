"""Interactive Session with .session()"""

# --- NATIVE ---
# Native ADK requires manual session lifecycle:
#   runner = InMemoryRunner(agent=agent, app_name="app")
#   session = await runner.session_service.create_session(...)
#   # Send messages manually with runner.run_async()
#   # No automatic cleanup

# --- FLUENT ---
from adk_fluent import Agent

# Context manager handles everything:
# async with Agent("chat").model("gemini-2.5-flash").instruct("Tutor.").session() as chat:
#     response1 = await chat.send("What is calculus?")
#     response2 = await chat.send("Give me an example.")

builder = Agent("chat").model("gemini-2.5-flash").instruct("Tutor.")

# --- ASSERT ---
assert hasattr(builder, "session")
assert callable(builder.session)

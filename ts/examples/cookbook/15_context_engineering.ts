/**
 * 15 — Context Engineering (C namespace)
 *
 * Control exactly what conversation context an agent sees. Background and
 * utility agents typically run with `C.none()` (no history); coordinator
 * agents run with `C.window(5)` to keep the last few turns.
 */
import assert from "node:assert/strict";
import { Agent, C } from "../../src/index.js";

// History-suppressing transforms — the agent sees ONLY its own instruction
// plus whatever the transform injects (no prior conversation).
const utility = new Agent("utility", "gemini-2.5-flash")
  .instruct("Format the input as JSON.")
  .context(C.none())
  .build() as Record<string, unknown>;
assert.equal(utility._type, "LlmAgent");

// Window keeps the last N turn-pairs.
const chatty = new Agent("chatty", "gemini-2.5-flash")
  .instruct("Continue the conversation.")
  .context(C.window(5))
  .build() as Record<string, unknown>;
assert.equal(chatty._type, "LlmAgent");

// Composition: suppress history but inject named state keys back as
// pseudo-messages. The `+` operator from Python is `.add()` in TS.
const focused = new Agent("focused", "gemini-2.5-flash")
  .instruct("Use only the provided briefing.")
  .context(C.none().union(C.fromState("briefing", "user_profile")))
  .build() as Record<string, unknown>;
assert.equal(focused._type, "LlmAgent");

export { utility, chatty, focused };

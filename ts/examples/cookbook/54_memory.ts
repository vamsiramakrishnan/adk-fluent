/**
 * 54 — Memory tools: `.memory()` and `.memoryAutoSave()`
 *
 * Two flags control how an agent interacts with the memory service:
 *   - `.memory(mode)`      — attach memory tools. Modes: "preload",
 *                            "on_demand", "both".
 *   - `.memoryAutoSave()`  — auto-save the session to memory after the
 *                            agent runs.
 *
 * Both are private config keys (`_memory`, `_memory_auto_save`) — the
 * runtime expands them into real ADK memory tools at execution time,
 * but they are stripped from the raw `.build()` output. Use
 * `.inspect()` to assert on them.
 */
import assert from "node:assert/strict";
import { Agent } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

// Default mode: "preload" — load relevant memories into context up-front.
const preloader = new Agent("preloader", MODEL)
  .instruct("Greet the returning user using anything you remember about them.")
  .memory();

assert.equal(preloader.inspect()._memory, "preload");
assert.equal(preloader.inspect()._memory_auto_save, undefined);

// On-demand mode: the LLM calls a memory tool only if it needs to.
const lazy = new Agent("lazy", MODEL)
  .instruct("Look up memories only if the user asks about past conversations.")
  .memory("on_demand");

assert.equal(lazy.inspect()._memory, "on_demand");

// Auto-save: persist this session into memory after the agent finishes.
const journaler = new Agent("journaler", MODEL)
  .instruct("Record what we discussed today.")
  .memory("both")
  .memoryAutoSave();

const journalerSnap = journaler.inspect();
assert.equal(journalerSnap._memory, "both");
assert.equal(journalerSnap._memory_auto_save, true);

// Build() strips the private keys — they don't leak into the ADK config.
const built = journaler.build() as Record<string, unknown>;
assert.equal(built._memory, undefined);
assert.equal(built._memory_auto_save, undefined);
assert.equal(built.name, "journaler");

export { preloader, lazy, journaler };

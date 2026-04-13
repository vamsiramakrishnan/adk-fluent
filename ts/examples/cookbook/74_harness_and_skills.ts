/**
 * 74 — Harness and Skills Integration
 *
 * Demonstrates how to compose harness primitives into a skill-powered
 * coding agent. Each primitive is independently testable and swappable:
 *
 *   - `H.hooks({workspace})` — hook registry for event-driven callbacks
 *   - `H.autoAllow(...)` / `H.askBefore(...)` — permission policies
 *   - `H.planMode()` — plan-then-execute latch
 *   - `H.sessionStore()` — session tape + fork management
 *   - `H.usage({costTable})` — token + cost tracking
 *   - `H.budgetMonitor(maxTokens)` — budget thresholds
 *
 * Ported from Python cookbook 78_harness_and_skills.py.
 */
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  Agent,
  H,
  HookEvent,
  HookDecision,
  PermissionMode,
} from "../../src/index.js";

const workspace = mkdtempSync(join(tmpdir(), "adk-fluent-74-"));

// ── Pattern 1: Hook registry for event-driven callbacks ──────────────

const registry = H.hooks(workspace);

// Subscribe to tool-use events. Hooks fire synchronously when the
// runner dispatches the matching event.
const toolsUsed: string[] = [];
registry.on(HookEvent.PreToolUse, (ctx) => {
  toolsUsed.push(ctx.toolName ?? "unknown");
  return HookDecision.allow();
});

// Subscribe to post-model events for observability.
let modelCallCount = 0;
registry.on(HookEvent.PostModel, () => {
  modelCallCount += 1;
  return HookDecision.allow();
});

assert.ok(registry, "Hook registry created");

// ── Pattern 2: Permission policies ───────────────────────────────────

// Compose allow + ask + deny layers. Deny > ask > allow.
const permissions = H.autoAllow("read_file", "glob_search", "grep_search", "list_dir")
  .merge(H.askBefore("edit_file", "write_file", "bash"))
  .merge(H.deny("rm_rf"));

assert.ok(permissions.allow.has("read_file"), "read_file is auto-allowed");
assert.ok(permissions.ask.has("bash"), "bash requires approval");
assert.ok(permissions.deny.has("rm_rf"), "rm_rf is denied");

// Check the decision API.
assert.ok(permissions.check("read_file").isAllow);
assert.ok(permissions.check("bash").isAsk);
assert.ok(permissions.check("rm_rf").isDeny);

// Permission modes override individual rules.
const planPermissions = permissions.withMode(PermissionMode.PLAN);
assert.ok(planPermissions.check("bash").isDeny, "PLAN mode denies mutating tools");
assert.ok(planPermissions.check("read_file").isAllow, "PLAN mode allows reads");

const bypassPermissions = permissions.withMode(PermissionMode.BYPASS);
assert.ok(bypassPermissions.check("rm_rf").isAllow, "BYPASS mode allows everything");

// ── Pattern 3: Plan mode latch ───────────────────────────────────────

const planMode = H.planMode();

assert.equal(planMode.current, "off");
assert.equal(planMode.isPlanning, false);

// Enter planning phase — mutating tools are blocked.
planMode.enter();
assert.equal(planMode.isPlanning, true);

// Exit with a plan — switches to executing phase.
planMode.exit("1. Read tests\n2. Fix bug\n3. Run tests");
assert.equal(planMode.isExecuting, true);
assert.ok(planMode.currentPlan.includes("Fix bug"));

// Subscribe to state changes.
const transitions: string[] = [];
planMode.subscribe((state) => transitions.push(state));
planMode.reset();
assert.deepEqual(transitions, ["off"]);

// Plan mode exposes LLM-callable tools.
const planTools = planMode.tools();
assert.equal(planTools.length, 2);

// ── Pattern 4: Session store (tape + forks) ──────────────────────────

const store = H.sessionStore();

// Record events into the session tape.
store.recordEvent({ kind: "tool_call_start", timestamp: Date.now(), toolName: "read_file" });
store.recordEvent({ kind: "tool_call_end", timestamp: Date.now(), toolName: "read_file" });
assert.equal(store.tape.events.length, 2);

// Fork state for speculative exploration.
store.fork("before-refactor", { draft: "v1", score: 0.6 });
store.fork("after-refactor", { draft: "v2", score: 0.9 });

// Switch between branches.
const restored = store.switch("before-refactor");
assert.equal(restored.draft, "v1");

// Snapshot for persistence.
const snapshot = store.snapshot();
assert.equal(snapshot.branchCount, 2);
assert.equal(snapshot.eventCount, 2);

// ── Pattern 5: Token usage + cost tracking ───────────────────────────

const costTable = H.costTable(
  new Map([
    ["gemini-2.5-pro", { inputPerMillion: 1.25, outputPerMillion: 5.0 }],
    ["gemini-2.5-flash", { inputPerMillion: 0.15, outputPerMillion: 0.6 }],
  ]),
);

const usage = H.usage({ costTable });

// Record model calls.
const rec1 = usage.record("gemini-2.5-pro", 10_000, 2_000);
assert.ok(rec1.costUsd > 0, "Pro model has a cost");

const rec2 = usage.record("gemini-2.5-flash", 10_000, 2_000);
assert.ok(rec2.costUsd < rec1.costUsd, "Flash is cheaper than Pro");

assert.equal(usage.totalInputTokens, 20_000);
assert.equal(usage.totalOutputTokens, 4_000);
assert.ok(usage.summary().includes("24,000"), "Summary includes total tokens");

// ── Pattern 6: Budget monitor with thresholds ────────────────────────

const warnings: number[] = [];
const compressions: number[] = [];

const monitor = H.budgetMonitor(200_000)
  .onThreshold(0.7, (m) => warnings.push(m.utilization))
  .onThreshold(0.9, (m) => compressions.push(m.utilization));

// Simulate 5 turns of usage (30k tokens each = 150k total).
for (let i = 0; i < 5; i++) {
  monitor.add(30_000);
}

// At 150k/200k = 75%, the 70% warning should have fired.
assert.equal(warnings.length, 1);
assert.ok(warnings[0] >= 0.7);

// Hit the 90% threshold.
monitor.add(30_000); // 180k total
assert.equal(compressions.length, 1);

// Reset clears counters and re-arms thresholds.
monitor.reset();
assert.equal(monitor.used, 0);

// ── Pattern 7: Full composition into a single agent ──────────────────

const agent = new Agent("coder", "gemini-2.5-pro")
  .instruct(
    "You are an expert coding assistant. " +
    "Read the codebase, edit files, run tests, and self-correct until done.",
  )
  .tools(H.workspace(workspace))
  .build() as Record<string, unknown>;

assert.equal(agent._type, "LlmAgent");

// The workspace tools are wired in.
const builtTools = agent.tools as unknown[];
assert.ok(builtTools.length > 0, "Agent has tools");

export {
  registry,
  permissions,
  planMode,
  store,
  usage,
  monitor,
  agent,
};

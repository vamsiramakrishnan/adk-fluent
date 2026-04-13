/**
 * 75 — Full Coding Agent Harness
 *
 * Builds a production-grade coding agent runtime using adk-fluent's
 * five-layer harness architecture:
 *
 *   1. INTELLIGENCE  — Agent + context engineering
 *   2. TOOLS         — Workspace, web, git, processes, code executor
 *   3. SAFETY        — Permissions, sandbox, budget, error recovery
 *   4. OBSERVABILITY — EventBus, tape, hooks, renderer
 *   5. RUNTIME       — REPL, slash commands, interrupt, tasks
 *
 * `H.codingAgent(workspace)` wires layers 1-3 into a single bundle.
 * This cookbook goes further, demonstrating every individual primitive
 * and how they compose into the complete system.
 *
 * Ported from Python cookbook 79_coding_agent_harness.py.
 */
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Agent, H, HookEvent, HookDecision } from "../../src/index.js";

const workspace = mkdtempSync(join(tmpdir(), "adk-fluent-75-"));

// Seed the workspace with sample files.
writeFileSync(join(workspace, "main.py"), "def greet(name):\n    return f'Hello, {name}!'\n");
writeFileSync(
  join(workspace, "test_main.py"),
  "from main import greet\n\ndef test_greet():\n    assert greet('World') == 'Hello, World!'\n",
);

// ═══════════════════════════════════════════════════════════════════════
// Layer 1: The all-in-one bundle (H.codingAgent)
// ═══════════════════════════════════════════════════════════════════════

const harness = H.codingAgent(workspace, {
  allowMutations: true,
  allowNetwork: true,
  enableGit: false, // no git repo in tmpdir
});

// The bundle exposes every primitive for swap-out / inspection.
assert.equal(harness.workspace, workspace);
assert.ok(Array.isArray(harness.tools));
assert.ok(harness.tools.length > 0, "Bundle includes tools");
assert.ok(harness.sandbox, "Bundle includes sandbox");
assert.ok(harness.permissions, "Bundle includes permissions");
assert.ok(harness.executor, "Bundle includes code executor");
assert.ok(harness.todos, "Bundle includes todo store");
assert.ok(harness.planMode, "Bundle includes plan mode");
assert.ok(harness.memory, "Bundle includes project memory");
assert.ok(harness.bus, "Bundle includes event bus");
assert.ok(harness.usage, "Bundle includes usage tracker");
assert.ok(harness.artifacts, "Bundle includes artifact store");
assert.ok(harness.approvalMemory, "Bundle includes approval memory");

// Git is disabled for this workspace.
assert.equal(harness.git, null);
assert.equal(harness.worktrees, null);

// ═══════════════════════════════════════════════════════════════════════
// Layer 2: Individual tool sets
// ═══════════════════════════════════════════════════════════════════════

// Workspace tools: read, edit, write, glob, grep, bash, ls.
const wsTools = H.workspace(workspace);
assert.ok(wsTools.length >= 7, `Expected 7+ workspace tools, got ${wsTools.length}`);

// Web tools: fetch + search.
const webToolsList = H.web();
assert.ok(webToolsList.length >= 1, "Web tools available");

// Process tools: start, check, stop.
const procTools = H.processes(workspace);
assert.ok(procTools.length >= 3, "Process tools available");

// Code executor: polyglot run_code + which_languages.
const executor = H.codeExecutor(workspace);
const execTools = executor.tools();
assert.ok(execTools.length >= 1, "Code executor exposes tools");

// ═══════════════════════════════════════════════════════════════════════
// Layer 3: Safety — permissions + sandbox + budget + error strategy
// ═══════════════════════════════════════════════════════════════════════

// Permission composition: allow > ask > deny precedence.
const permissions = H.autoAllow("read_file", "glob_search", "grep_search", "list_dir")
  .merge(H.askBefore("edit_file", "write_file", "bash"))
  .merge(H.deny("rm_rf"));

assert.ok(permissions.check("read_file").isAllow);
assert.ok(permissions.check("bash").isAsk);
assert.ok(permissions.check("rm_rf").isDeny);

// Pattern-based permissions for large tool sets.
const patternPerms = H.allowPatterns(["read_*", "list_*"]).merge(
  H.denyPatterns(["*_delete", "*_destroy"]),
);
assert.ok(patternPerms.allowPatterns.length > 0);
assert.ok(patternPerms.denyPatterns.length > 0);

// Sandbox policy confines file ops to the workspace.
const sandbox = H.sandbox({
  workspace,
  allowShell: true,
  allowNetwork: true,
  readPaths: ["/usr/share/dict"],
});
assert.equal(sandbox.workspace, workspace);
assert.ok(sandbox.allowShell);

// Budget monitor with threshold callbacks.
const warnings: number[] = [];
const monitor = H.budgetMonitor(200_000)
  .onThreshold(0.7, (m) => warnings.push(m.utilization))
  .onThreshold(0.9, (m) => warnings.push(m.utilization));

for (let i = 0; i < 5; i++) {
  monitor.add(30_000); // 150k total
}
assert.equal(warnings.length, 1, "70% threshold fired");

monitor.add(30_000); // 180k total
assert.equal(warnings.length, 2, "90% threshold fired");

// Tool policy: per-tool error recovery.
const toolPolicy = H.toolPolicy()
  .retry("bash", { maxAttempts: 3, backoff: 1.0 })
  .retry("web_fetch", { maxAttempts: 2, backoff: 0.5 })
  .skip("glob_search", { fallback: "No matching files found." });

assert.equal(toolPolicy.ruleFor("bash").action, "retry");
assert.equal(toolPolicy.ruleFor("bash").maxAttempts, 3);
assert.equal(toolPolicy.ruleFor("glob_search").action, "skip");
assert.equal(toolPolicy.ruleFor("unknown_tool").action, "propagate");

// Error strategy: retry/skip sets.
const errorStrategy = H.onError({
  retry: ["bash", "web_fetch"],
  skip: ["glob_search"],
});
assert.ok(errorStrategy, "Error strategy created");

// ═══════════════════════════════════════════════════════════════════════
// Layer 4: Observability — EventBus + tape + hooks + renderer
// ═══════════════════════════════════════════════════════════════════════

// EventBus is the single observer backbone.
const bus = H.eventBus({ maxBuffer: 100 });
const busEvents: string[] = [];
bus.on("tool_call_start", (e) => busEvents.push((e as { toolName?: string }).toolName ?? "?"));

bus.emit({ kind: "tool_call_start", timestamp: Date.now(), toolName: "read_file" });
bus.emit({ kind: "tool_call_end", timestamp: Date.now(), toolName: "read_file", durationMs: 42 });
assert.deepEqual(busEvents, ["read_file"]);

// Session tape records events for replay.
const tape = H.tape({ maxEvents: 1000 });
tape.record({ kind: "tool_call_start", timestamp: Date.now(), toolName: "bash" });
tape.record({ kind: "tool_call_end", timestamp: Date.now(), toolName: "bash", durationMs: 100 });
assert.equal(tape.events.length, 2);

// Hook registry for user-defined hooks.
const hooks = H.hooks(workspace);
const hookLog: string[] = [];
hooks.on(HookEvent.PreToolUse, (ctx) => {
  hookLog.push(`pre:${ctx.toolName}`);
  return HookDecision.allow();
});
hooks.on(HookEvent.PostToolUse, (ctx) => {
  hookLog.push(`post:${ctx.toolName}`);
  return HookDecision.allow();
});
assert.ok(hooks, "Hook registry created with subscribers");

// Event renderer converts events to display strings.
const renderer = H.renderer("plain", { showTiming: true });
assert.ok(renderer, "Renderer created");

// ═══════════════════════════════════════════════════════════════════════
// Layer 5: Runtime — commands + cancellation + tasks + context compress
// ═══════════════════════════════════════════════════════════════════════

// Slash commands for the REPL.
const cmds = H.commands();
cmds.register("clear", () => "Context cleared.", "Clear context");
cmds.register("model", (args) => `Model: ${args}`, "Switch model");
cmds.register("compact", () => "Compacted.", "Compress context");

assert.ok(cmds.isCommand("/clear"));
assert.ok(!cmds.isCommand("not a command"));

// List registered commands for introspection.
const registeredCmds = cmds.list();
assert.ok(registeredCmds.length >= 3);
assert.ok(registeredCmds.some((c) => c.name === "clear"));

// Cancellation token for cooperative interrupt.
const token = H.cancellationToken();
assert.equal(token.cancelled, false);
token.cancel();
assert.equal(token.cancelled, true);
token.reset();
assert.equal(token.cancelled, false);

// Task ledger for LLM-managed background tasks.
const ledger = H.taskLedger({ maxTasks: 5 });
const taskTools = ledger.tools();
assert.ok(taskTools.length >= 2, "Task ledger exposes tools");

// Context compressor for auto-compression.
const compressor = H.compressor({ threshold: 100_000 });
assert.ok(compressor.shouldCompress(150_000));
assert.ok(!compressor.shouldCompress(50_000));

// ═══════════════════════════════════════════════════════════════════════
// Full assembly: wire the bundle into an Agent
// ═══════════════════════════════════════════════════════════════════════

const coder = new Agent("coder", "gemini-2.5-pro")
  .instruct(
    "You are an expert coding assistant. " +
    "Use the provided tools to read files, edit code, run tests, " +
    "and manage background tasks.",
  )
  .tools(harness.tools)
  .build() as Record<string, unknown>;

assert.equal(coder._type, "LlmAgent");

// Tools are wired through the bundle.
const builtTools = coder.tools as unknown[];
assert.equal(builtTools.length, 1, "tools() wraps the array as a single entry");
assert.equal(
  (builtTools[0] as unknown[]).length,
  harness.tools.length,
  "Inner array matches bundle tool count",
);

// Plan mode is independently accessible.
assert.equal(harness.planMode.current, "off");
harness.planMode.enter();
assert.equal(harness.planMode.isPlanning, true);
harness.planMode.reset();

// Todos are independently accessible.
harness.todos.replace([
  { content: "Read codebase", activeForm: "Reading codebase", status: "completed" },
  { content: "Fix auth bug", activeForm: "Fixing auth bug", status: "in_progress" },
  { content: "Write tests", activeForm: "Writing tests", status: "pending" },
]);
assert.equal(harness.todos.list().length, 3);

// Usage tracker records model calls.
harness.usage.record("gemini-2.5-pro", 5_000, 2_000);
assert.equal(harness.usage.totalTokens, 7_000);

export {
  harness,
  coder,
  bus,
  cmds,
  monitor,
  toolPolicy,
  compressor,
};

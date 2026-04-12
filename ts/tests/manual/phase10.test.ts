/**
 * Phase 10 — TypeScript port of the Python-side mechanisms from Phases
 * 1-9. Covers PermissionMode/PermissionDecision, the promoted PlanMode
 * latch + PlanModePolicy, SessionStore + SessionSnapshot, CostTable /
 * AgentUsage, BudgetPolicy, and the ContextCompressor pre-compact hook.
 */

import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { H } from "../../src/namespaces/harness/H.js";
import {
  PermissionMode,
  PermissionBehavior,
  PermissionDecision,
  PermissionPolicy,
} from "../../src/namespaces/harness/permissions.js";
import {
  PlanMode,
  PlanModePolicy,
  planModeBeforeToolHook,
  MUTATING_TOOLS,
} from "../../src/namespaces/harness/plan-mode.js";
import { SessionStore, SessionSnapshot } from "../../src/namespaces/harness/session-store.js";
import { CostTable, TurnUsage, AgentUsage } from "../../src/namespaces/harness/usage.js";
import {
  BudgetPolicy,
  BudgetMonitor,
  ContextCompressor,
} from "../../src/namespaces/harness/lifecycle.js";

// ─── permissions: modes + decisions ────────────────────────────────────────

describe("permissions / modes + decisions", () => {
  it("default mode yields allow for unknown tools", () => {
    const policy = new PermissionPolicy();
    const d = policy.check("read_file");
    expect(d).toBeInstanceOf(PermissionDecision);
    expect(d.isAllow).toBe(true);
    expect(d.behavior).toBe(PermissionBehavior.ALLOW);
  });

  it("ask set produces an ASK decision with reason", () => {
    const policy = new PermissionPolicy({ ask: ["bash"] });
    const d = policy.check("bash");
    expect(d.isAsk).toBe(true);
    expect(d.reason).toContain("bash");
  });

  it("deny set wins over ask/allow", () => {
    const policy = new PermissionPolicy({ deny: ["rm"], allow: ["rm"] });
    expect(policy.check("rm").isDeny).toBe(true);
  });

  it("withMode(PLAN) denies mutating tools", () => {
    const base = new PermissionPolicy({ allow: ["write_file"] });
    const planned = base.withMode(PermissionMode.PLAN);
    const d = planned.check("write_file");
    expect(d.isDeny).toBe(true);
    expect(d.reason).toContain("Plan mode");
    expect(d.mode).toBe(PermissionMode.PLAN);
  });

  it("withMode(BYPASS) allows everything", () => {
    const policy = new PermissionPolicy({ deny: ["bash"] }).withMode(PermissionMode.BYPASS);
    expect(policy.check("bash").isAllow).toBe(true);
  });

  it("withMode(ACCEPT_EDITS) auto-allows write/edit tools", () => {
    const policy = new PermissionPolicy({ ask: ["edit_file"] }).withMode(
      PermissionMode.ACCEPT_EDITS,
    );
    expect(policy.check("edit_file").isAllow).toBe(true);
  });

  it("decide() still returns the plain verdict string", () => {
    const policy = new PermissionPolicy({ ask: ["bash"] });
    expect(policy.decide("bash")).toBe("ask");
  });

  it("PermissionDecision is frozen", () => {
    const d = PermissionDecision.allow("ok");
    expect(() => {
      // @ts-expect-error frozen assignment should throw in strict mode
      d.reason = "mutated";
    }).toThrow();
  });
});

// ─── plan mode: latch + observers + policy + before-tool hook ─────────────

describe("plan mode / latch", () => {
  it("starts in off state", () => {
    const latch = new PlanMode();
    expect(latch.current).toBe("off");
    expect(latch.isPlanning).toBe(false);
  });

  it("enter -> planning, exit captures plan", () => {
    const latch = new PlanMode();
    latch.enter();
    expect(latch.isPlanning).toBe(true);
    latch.exit("1. Do X\n2. Do Y");
    expect(latch.isExecuting).toBe(true);
    expect(latch.currentPlan).toContain("Do X");
  });

  it("observers fire on every transition", () => {
    const latch = new PlanMode();
    const events: Array<[string, string]> = [];
    latch.subscribe((state, plan) => events.push([state, plan]));
    latch.enter();
    latch.exit("plan");
    latch.reset();
    expect(events).toEqual([
      ["planning", ""],
      ["executing", "plan"],
      ["off", ""],
    ]);
  });

  it("unsubscribe stops notifications", () => {
    const latch = new PlanMode();
    const events: string[] = [];
    const unsub = latch.subscribe((s) => events.push(s));
    latch.enter();
    unsub();
    latch.exit("x");
    expect(events).toEqual(["planning"]);
  });

  it("broken observer does not break the latch", () => {
    const latch = new PlanMode();
    latch.subscribe(() => {
      throw new Error("boom");
    });
    expect(() => latch.enter()).not.toThrow();
    expect(latch.isPlanning).toBe(true);
  });

  it("isMutating classifies tool names against the frozen set", () => {
    expect(PlanMode.isMutating("write_file")).toBe(true);
    expect(PlanMode.isMutating("read_file")).toBe(false);
    expect(MUTATING_TOOLS.has("bash")).toBe(true);
  });

  it("tools() returns enter/exit pair bound to the latch", async () => {
    const latch = new PlanMode();
    const [enter, exit] = latch.tools();
    expect(enter.toolName).toBe("enter_plan_mode");
    expect(exit.toolName).toBe("exit_plan_mode");
    await enter({});
    expect(latch.isPlanning).toBe(true);
    await exit({ plan: "step" });
    expect(latch.isExecuting).toBe(true);
  });
});

describe("plan mode / PlanModePolicy", () => {
  it("off state delegates to base policy", () => {
    const base = new PermissionPolicy({ allow: ["write_file"] });
    const latch = new PlanMode();
    const policy = new PlanModePolicy(base, latch);
    expect(policy.check("write_file").isAllow).toBe(true);
    expect(policy.mode).toBe(PermissionMode.DEFAULT);
  });

  it("planning state denies mutating tools", () => {
    const base = new PermissionPolicy({ allow: ["write_file"] });
    const latch = new PlanMode();
    const policy = new PlanModePolicy(base, latch);
    latch.enter();
    expect(policy.check("write_file").isDeny).toBe(true);
    expect(policy.mode).toBe(PermissionMode.PLAN);
  });

  it("exiting returns to base behaviour", () => {
    const base = new PermissionPolicy({ allow: ["write_file"] });
    const latch = new PlanMode();
    const policy = new PlanModePolicy(base, latch);
    latch.enter();
    latch.exit("done");
    expect(policy.check("write_file").isAllow).toBe(true);
  });

  it("H.planModePolicy is the factory shortcut", () => {
    const policy = H.planModePolicy(new PermissionPolicy());
    expect(policy).toBeInstanceOf(PlanModePolicy);
  });
});

describe("plan mode / before-tool hook", () => {
  it("returns null when latch is off", () => {
    const latch = new PlanMode();
    const hook = planModeBeforeToolHook(latch);
    expect(hook("write_file")).toBeNull();
  });

  it("blocks mutating tools while planning", () => {
    const latch = new PlanMode();
    latch.enter();
    const hook = planModeBeforeToolHook(latch);
    const result = hook("write_file");
    expect(result).not.toBeNull();
    expect(result!.error).toContain("Plan mode");
    expect(result!.planModeState).toBe("planning");
  });

  it("allows read tools while planning", () => {
    const latch = new PlanMode();
    latch.enter();
    const hook = planModeBeforeToolHook(latch);
    expect(hook("read_file")).toBeNull();
  });
});

// ─── session store: tape + forks + snapshot ────────────────────────────────

describe("session store / SessionStore", () => {
  let tmp: string;
  beforeAll(() => {
    tmp = mkdtempSync(join(tmpdir(), "adk-ts-session-"));
  });
  afterAll(() => {
    rmSync(tmp, { recursive: true, force: true });
  });

  it("records events into the tape", () => {
    const store = new SessionStore();
    store.recordEvent({
      kind: "text",
      text: "hello",
      timestamp: Date.now(),
    });
    expect(store.tape.events).toHaveLength(1);
  });

  it("forks and switches branches", () => {
    const store = new SessionStore();
    store.fork("v1", { draft: "a" });
    store.fork("v2", { draft: "b" });
    const state = store.switch("v1");
    expect(state.draft).toBe("a");
    expect(store.activeBranch).toBe("v1");
  });

  it("snapshot captures both tape and branches", () => {
    const store = new SessionStore();
    store.recordEvent({ kind: "text", text: "hi", timestamp: 1 });
    store.fork("v1", { x: 1 });
    const snap = store.snapshot();
    expect(snap).toBeInstanceOf(SessionSnapshot);
    expect(snap.events).toHaveLength(1);
    expect(Object.keys(snap.branches)).toContain("v1");
  });

  it("fromSnapshot rehydrates a new store", () => {
    const store = new SessionStore();
    store.recordEvent({ kind: "text", text: "one", timestamp: 1 });
    store.fork("v1", { x: 42 });
    const snap = store.snapshot();
    const rebuilt = SessionStore.fromSnapshot(snap);
    expect(rebuilt.tape.events).toHaveLength(1);
    expect(rebuilt.switch("v1").x).toBe(42);
  });

  it("save/load round-trips through JSON", () => {
    const store = new SessionStore();
    store.recordEvent({ kind: "text", text: "persist", timestamp: 1 });
    store.fork("v1", { y: 7 });
    const path = join(tmp, "session.json");
    store.snapshot().save(path);
    const loaded = SessionSnapshot.load(path);
    expect(loaded.events).toHaveLength(1);
    const rebuilt = SessionStore.fromSnapshot(loaded);
    expect(rebuilt.switch("v1").y).toBe(7);
  });

  it("SessionSnapshot is frozen", () => {
    const snap = new SessionSnapshot();
    expect(() => {
      // @ts-expect-error frozen assignment
      snap.version = 99;
    }).toThrow();
  });

  it("summary reports counts and active branch", () => {
    const store = new SessionStore();
    store.fork("v1", { a: 1 });
    store.switch("v1");
    const s = store.summary();
    expect(s.branchCount).toBe(1);
    expect(s.activeBranch).toBe("v1");
  });

  it("H.sessionStore is the factory", () => {
    expect(H.sessionStore()).toBeInstanceOf(SessionStore);
  });
});

// ─── usage: cost table + agent accumulators ────────────────────────────────

describe("usage / CostTable", () => {
  it("looks up per-model rates and falls back to default", () => {
    const table = new CostTable(
      [["gemini-2.5-pro", { inputPerMillion: 1.25, outputPerMillion: 5.0 }]],
      { inputPerMillion: 0.5, outputPerMillion: 1.0 },
    );
    expect(table.rateFor("gemini-2.5-pro").inputPerMillion).toBe(1.25);
    expect(table.rateFor("unknown").inputPerMillion).toBe(0.5);
  });

  it("computes cost in USD for a model call", () => {
    const table = CostTable.flat(2.0, 8.0);
    const cost = table.cost("any", 1_000_000, 500_000);
    expect(cost).toBeCloseTo(2.0 + 4.0, 5);
  });

  it("H.flatCostTable is a shortcut", () => {
    const table = H.flatCostTable(1, 2);
    expect(table.rateFor("any").inputPerMillion).toBe(1);
  });
});

describe("usage / AgentUsage", () => {
  it("accumulates tokens across turns", () => {
    const agent = new AgentUsage("coder");
    agent.turn(0).add(100, 50, 0.01);
    agent.turn(1).add(200, 80, 0.02);
    expect(agent.inputTokens).toBe(300);
    expect(agent.outputTokens).toBe(130);
    expect(agent.totalTokens).toBe(430);
    expect(agent.costUsd).toBeCloseTo(0.03, 5);
  });

  it("TurnUsage tracks model calls", () => {
    const turn = new TurnUsage();
    turn.add(10, 5, 0.001);
    turn.add(20, 8, 0.002);
    expect(turn.modelCalls).toBe(2);
    expect(turn.totalTokens).toBe(43);
  });

  it("UsageTracker exposes forAgent accumulators", () => {
    const tracker = H.usage();
    const agent = tracker.forAgent("coder");
    expect(agent).toBeInstanceOf(AgentUsage);
    expect(tracker.forAgent("coder")).toBe(agent);
  });
});

// ─── budget policy + pre-compact hook ──────────────────────────────────────

describe("lifecycle / BudgetPolicy", () => {
  it("freezes thresholds and applies them to a monitor", () => {
    const policy = new BudgetPolicy({
      maxTokens: 10_000,
      thresholds: [{ ratio: 0.5 }, { ratio: 0.9, label: "critical" }],
    });
    const monitor = new BudgetMonitor(policy.maxTokens);
    const fired: number[] = [];
    policy.applyTo(monitor, (m) => fired.push(m.utilization));
    monitor.update(5_000);
    monitor.update(9_500);
    expect(fired).toHaveLength(2);
  });

  it("BudgetPolicy is frozen", () => {
    const policy = new BudgetPolicy({ maxTokens: 100 });
    expect(() => {
      // @ts-expect-error frozen
      policy.maxTokens = 200;
    }).toThrow();
  });

  it("H.budgetPolicy is the factory", () => {
    const policy = H.budgetPolicy(50_000, [{ ratio: 0.8 }]);
    expect(policy.thresholds).toHaveLength(1);
    expect(policy.maxTokens).toBe(50_000);
  });
});

describe("lifecycle / ContextCompressor pre-compact hook", () => {
  it("runs preCompact before compressing", async () => {
    const seen: unknown[] = [];
    const compressor = new ContextCompressor({
      threshold: 10,
      preCompact: (msgs) => {
        seen.push(...msgs);
      },
    });
    const out = await compressor.compressMessages([1, 2, 3, 4, 5]);
    expect(seen).toEqual([1, 2, 3, 4, 5]);
    expect(out.length).toBeLessThan(5);
  });

  it("swallows preCompact errors", async () => {
    const compressor = new ContextCompressor({
      preCompact: () => {
        throw new Error("boom");
      },
    });
    await expect(compressor.compressMessages([1, 2, 3, 4])).resolves.toBeDefined();
  });
});

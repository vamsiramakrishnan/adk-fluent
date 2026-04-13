/**
 * Parity tests for the Python-parity harness sub-packages ported to TS:
 *   - subagents (SubagentSpec, SubagentRegistry, FakeSubagentRunner, makeTaskTool)
 *   - fs (LocalBackend, MemoryBackend, SandboxedBackend)
 *   - hooks (HookEvent, HookDecision, HookMatcher, SystemMessageChannel, HookRegistry.dispatch)
 *   - session (Branch, ForkRegistry, SessionSnapshot, SessionStore, SessionPlugin)
 */
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import {
  SubagentSpec,
  SubagentRegistry,
  SubagentResult,
  FakeSubagentRunner,
  makeTaskTool,
} from "../../src/namespaces/harness/subagents.js";
import {
  LocalBackend,
  MemoryBackend,
  SandboxedBackend,
  SandboxViolation,
} from "../../src/namespaces/harness/fs.js";
import { SandboxPolicy } from "../../src/namespaces/harness/sandbox.js";
import {
  HookEvent,
  HookDecision,
  HookMatcher,
  HookRegistry,
  SystemMessageChannel,
  SYSTEM_MESSAGE_STATE_KEY,
} from "../../src/namespaces/harness/registries.js";
import {
  Branch,
  ForkRegistry,
  SessionSnapshot,
  SessionStore,
  SessionPlugin,
} from "../../src/namespaces/harness/session-store.js";
import { H } from "../../src/namespaces/harness/H.js";

// ─── subagents ─────────────────────────────────────────────────────────────

describe("subagents — SubagentSpec", () => {
  it("freezes spec fields", () => {
    const spec = new SubagentSpec({
      role: "researcher",
      instruction: "Find papers",
      description: "Deep research",
      toolNames: ["search", "read"],
    });
    expect(spec.role).toBe("researcher");
    expect(spec.toolNames).toEqual(["search", "read"]);
    expect(Object.isFrozen(spec)).toBe(true);
  });

  it("rejects empty role/instruction", () => {
    expect(() => new SubagentSpec({ role: "", instruction: "x" })).toThrow();
    expect(() => new SubagentSpec({ role: "r", instruction: "" })).toThrow();
  });
});

describe("subagents — SubagentRegistry", () => {
  it("refuses duplicate roles but allows replace", () => {
    const reg = new SubagentRegistry();
    reg.register(new SubagentSpec({ role: "a", instruction: "x" }));
    expect(() =>
      reg.register(new SubagentSpec({ role: "a", instruction: "y" })),
    ).toThrow();
    reg.replace(new SubagentSpec({ role: "a", instruction: "z" }));
    expect(reg.require("a").instruction).toBe("z");
  });

  it("roster enumerates role + description", () => {
    const reg = new SubagentRegistry([
      new SubagentSpec({
        role: "r1",
        instruction: "a",
        description: "researcher",
      }),
      new SubagentSpec({ role: "r2", instruction: "b" }),
    ]);
    const roster = reg.roster();
    expect(roster).toContain("r1: researcher");
    expect(roster).toContain("r2:");
    expect(reg.size).toBe(2);
    expect(reg.has("r1")).toBe(true);
  });
});

describe("subagents — FakeSubagentRunner + makeTaskTool", () => {
  it("runs the responder and records calls", () => {
    const runner = new FakeSubagentRunner({
      responder: (_s, prompt) => `ok: ${prompt}`,
      usage: { input: 10, output: 5 },
    });
    const reg = new SubagentRegistry([
      new SubagentSpec({ role: "writer", instruction: "Write" }),
    ]);
    const task = makeTaskTool(reg, runner);
    const out = task("writer", "hello");
    expect(out).toBe("[writer] ok: hello");
    expect(runner.calls.length).toBe(1);
    expect(runner.calls[0].prompt).toBe("hello");
  });

  it("returns error string for unknown role", () => {
    const task = makeTaskTool(new SubagentRegistry(), new FakeSubagentRunner());
    expect(task("ghost", "hi")).toMatch(/unknown subagent role 'ghost'/);
  });

  it("errorForRole surfaces as [role:error] output", () => {
    const runner = new FakeSubagentRunner({
      errorForRole: { bad: "boom" },
    });
    const reg = new SubagentRegistry([
      new SubagentSpec({ role: "bad", instruction: "x" }),
    ]);
    const task = makeTaskTool(reg, runner);
    expect(task("bad", "go")).toBe("[bad:error] boom");
  });

  it("task tool description enumerates registered roles", () => {
    const reg = new SubagentRegistry([
      new SubagentSpec({
        role: "r1",
        instruction: "a",
        description: "desc-one",
      }),
    ]);
    const task = makeTaskTool(reg, new FakeSubagentRunner());
    expect(task.description).toContain("r1: desc-one");
  });

  it("SubagentResult.toToolOutput formats success + error", () => {
    const ok = new SubagentResult({ role: "r", output: "hi" });
    expect(ok.toToolOutput()).toBe("[r] hi");
    expect(ok.isError).toBe(false);
    const err = new SubagentResult({ role: "r", output: "", error: "nope" });
    expect(err.toToolOutput()).toBe("[r:error] nope");
    expect(err.isError).toBe(true);
  });
});

// ─── fs ────────────────────────────────────────────────────────────────────

describe("fs — MemoryBackend", () => {
  it("writes, reads, lists, and deletes", () => {
    const be = new MemoryBackend();
    be.writeText("/a/b.txt", "hello");
    expect(be.exists("/a/b.txt")).toBe(true);
    expect(be.readText("/a/b.txt")).toBe("hello");
    expect(be.stat("/a/b.txt").size).toBe(5);
    const entries = be.listDir("/a");
    expect(entries.map((e) => e.name)).toContain("b.txt");
    be.delete_("/a/b.txt");
    expect(be.exists("/a/b.txt")).toBe(false);
  });

  it("normalises `..` traversal and seeds from constructor", () => {
    const be = new MemoryBackend({ "/x/y.txt": "42" });
    expect(be.readText("/x/y.txt")).toBe("42");
    // `..` reduction
    expect(be.readText("/x/../x/y.txt")).toBe("42");
  });

  it("throws ENOENT for missing file", () => {
    const be = new MemoryBackend();
    expect(() => be.readText("/missing")).toThrow(/ENOENT/);
  });
});

describe("fs — LocalBackend + SandboxedBackend", () => {
  it("LocalBackend reads/writes a real file", () => {
    const dir = mkdtempSync(join(tmpdir(), "parity-fs-"));
    try {
      const be = new LocalBackend(dir);
      be.writeText("hello.txt", "world");
      expect(be.readText("hello.txt")).toBe("world");
      expect(be.exists("hello.txt")).toBe(true);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("SandboxedBackend refuses escapes outside workspace", () => {
    const inner = new MemoryBackend();
    const sandbox = new SandboxPolicy({ workspace: "/ws" });
    const be = new SandboxedBackend(inner, sandbox);
    be.writeText("/ws/ok.txt", "yes");
    expect(be.readText("/ws/ok.txt")).toBe("yes");
    expect(() => be.writeText("/etc/passwd", "nope")).toThrow(SandboxViolation);
    expect(() => be.readText("/etc/passwd")).toThrow(SandboxViolation);
  });
});

// ─── hooks ─────────────────────────────────────────────────────────────────

describe("hooks — HookDecision factories", () => {
  it("allow/deny/modify/replace/ask/inject set fields and predicates", () => {
    expect(HookDecision.allow().isAllow).toBe(true);
    expect(HookDecision.deny("nope").action).toBe("deny");
    expect(HookDecision.deny("nope").isTerminal).toBe(true);
    expect(HookDecision.modify({ a: 1 }).toolInput).toEqual({ a: 1 });
    expect(HookDecision.replace(42).output).toBe(42);
    expect(HookDecision.ask("why?").prompt).toBe("why?");
    expect(HookDecision.inject("note").systemMessage).toBe("note");
    expect(HookDecision.inject("note").isSideEffect).toBe(true);
  });
});

describe("hooks — HookMatcher", () => {
  it("matches by event + tool name regex", () => {
    const m = HookMatcher.forTool(HookEvent.PreToolUse, "bash");
    expect(
      m.matches({ event: HookEvent.PreToolUse, toolName: "bash" }),
    ).toBe(true);
    expect(
      m.matches({ event: HookEvent.PreToolUse, toolName: "write_file" }),
    ).toBe(false);
    expect(m.matches({ event: HookEvent.PostToolUse, toolName: "bash" })).toBe(
      false,
    );
  });

  it("applies fnmatch globs to toolInput values", () => {
    const m = new HookMatcher({
      event: HookEvent.PreToolUse,
      toolName: "write_file",
      args: { path: "/secret/*" },
    });
    expect(
      m.matches({
        event: HookEvent.PreToolUse,
        toolName: "write_file",
        toolInput: { path: "/secret/keys.txt" },
      }),
    ).toBe(true);
    expect(
      m.matches({
        event: HookEvent.PreToolUse,
        toolName: "write_file",
        toolInput: { path: "/public/readme" },
      }),
    ).toBe(false);
  });

  it("rejects unknown events", () => {
    expect(() => new HookMatcher({ event: "bogus" })).toThrow();
  });
});

describe("hooks — HookRegistry.dispatch", () => {
  it("first terminal decision wins and short-circuits the chain", async () => {
    const reg = new HookRegistry();
    let laterRan = false;
    reg.on(HookEvent.PreToolUse, () => HookDecision.deny("blocked"));
    reg.on(HookEvent.PreToolUse, () => {
      laterRan = true;
      return HookDecision.allow();
    });
    const decision = await reg.dispatch({ event: HookEvent.PreToolUse });
    expect(decision.action).toBe("deny");
    expect(decision.reason).toBe("blocked");
    expect(laterRan).toBe(false);
  });

  it("modify decisions rewrite ctx.toolInput for downstream hooks", async () => {
    const reg = new HookRegistry();
    reg.on(HookEvent.PreToolUse, () => HookDecision.modify({ path: "/safe" }));
    let seen: unknown = null;
    reg.on(HookEvent.PreToolUse, (ctx) => {
      seen = ctx.toolInput?.path;
      return HookDecision.allow();
    });
    const ctx = {
      event: HookEvent.PreToolUse,
      toolName: "write_file",
      toolInput: { path: "/unsafe" },
    };
    await reg.dispatch(ctx);
    expect(seen).toBe("/safe");
    expect(ctx.toolInput.path).toBe("/safe");
  });

  it("inject decisions accumulate into pendingInjects metadata", async () => {
    const reg = new HookRegistry();
    reg.on(HookEvent.PreToolUse, () => HookDecision.inject("msg-a"));
    reg.on(HookEvent.PreToolUse, () => HookDecision.inject("msg-b"));
    const decision = await reg.dispatch({ event: HookEvent.PreToolUse });
    expect(decision.isAllow).toBe(true);
    expect(decision.metadata.pendingInjects).toEqual(["msg-a", "msg-b"]);
  });

  it("throws errors as deny with reason prefix", async () => {
    const reg = new HookRegistry();
    reg.on(HookEvent.PreToolUse, () => {
      throw new Error("boom");
    });
    const decision = await reg.dispatch({ event: HookEvent.PreToolUse });
    expect(decision.action).toBe("deny");
    expect(decision.reason).toContain("boom");
  });
});

describe("hooks — SystemMessageChannel", () => {
  it("append/peek/drain round-trip through state", () => {
    const state: Record<string, unknown> = {};
    const ch = new SystemMessageChannel(state);
    ch.append("one");
    ch.append("two");
    expect(ch.pendingCount).toBe(2);
    expect(ch.peek()).toEqual(["one", "two"]);
    expect(ch.drain()).toEqual(["one", "two"]);
    expect(ch.pendingCount).toBe(0);
    expect(state[SYSTEM_MESSAGE_STATE_KEY]).toEqual([]);
  });

  it("handles missing state gracefully", () => {
    const ch = new SystemMessageChannel(undefined);
    ch.append("lost");
    expect(ch.peek()).toEqual([]);
    expect(ch.pendingCount).toBe(0);
  });
});

// ─── session ───────────────────────────────────────────────────────────────

describe("session — Branch.toDict/fromDict round-trips", () => {
  it("preserves state, messages, parent, metadata", () => {
    const b = new Branch({
      name: "draft-v1",
      state: { draft: "hello" },
      messages: [{ role: "user", content: "hi" }],
      parent: "main",
      metadata: { tag: "experiment" },
    });
    const data = b.toDict();
    expect(data.name).toBe("draft-v1");
    expect((data.state as Record<string, unknown>).draft).toBe("hello");
    const b2 = Branch.fromDict(data);
    expect(b2.name).toBe("draft-v1");
    expect(b2.parent).toBe("main");
    expect(b2.metadata.tag).toBe("experiment");
    expect(b2.messages[0]?.content).toBe("hi");
  });
});

describe("session — ForkRegistry", () => {
  it("fork/switch/merge/diff", () => {
    const forks = new ForkRegistry();
    forks.fork("a", { x: 1, y: 2 });
    forks.fork("b", { x: 9, z: 3 });

    // Union: b wins on x since it's last, plus z from b
    const union = forks.merge(["a", "b"]);
    expect(union).toEqual({ x: 9, y: 2, z: 3 });

    // Intersection: only x (common key), last-branch value
    const intersect = forks.merge(["a", "b"], { strategy: "intersection" });
    expect(intersect).toEqual({ x: 9 });

    // Prefer: overlay a on top
    const prefer = forks.merge(["a", "b"], { strategy: "prefer", prefer: "a" });
    expect(prefer.x).toBe(1);

    // Diff
    const d = forks.diff("a", "b");
    expect(d.onlyA).toEqual({ y: 2 });
    expect(d.onlyB).toEqual({ z: 3 });
    expect(d.different.x).toEqual({ a: 1, b: 9 });
  });

  it("switch returns a deep clone and tracks active branch", () => {
    const forks = new ForkRegistry();
    forks.fork("main", { doc: { body: "v1" } });
    const state = forks.switch("main") as { doc: { body: string } };
    state.doc.body = "mutated";
    // Original branch state must be untouched.
    expect(
      (forks.get("main").state as { doc: { body: string } }).doc.body,
    ).toBe("v1");
    expect(forks.active).toBe("main");
  });

  it("throws for unknown branch on switch", () => {
    const forks = new ForkRegistry();
    expect(() => forks.switch("ghost")).toThrow();
  });
});

describe("session — SessionSnapshot round-trip", () => {
  it("save/load preserves events + branches + activeBranch", () => {
    const store = new SessionStore();
    store.fork("base", { draft: "v1" });
    store.fork("refactor", { draft: "v2" }, { parent: "base" });
    const snap = store.snapshot();

    const dir = mkdtempSync(join(tmpdir(), "parity-session-"));
    try {
      const path = join(dir, "snap.json");
      snap.save(path);
      const loaded = SessionSnapshot.load(path);
      expect(loaded.branchCount).toBe(2);
      expect(loaded.activeBranch).toBe("refactor");
      expect(loaded.branches.refactor.parent).toBe("base");

      const store2 = SessionStore.fromSnapshot(loaded);
      expect(store2.forks.has("base")).toBe(true);
      expect(store2.forks.has("refactor")).toBe(true);
      expect(store2.activeBranch).toBe("refactor");
      expect(
        (store2.forks.get("refactor").state as { draft: string }).draft,
      ).toBe("v2");
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("snake_case fields in toDict are Python-portable", () => {
    const snap = new SessionSnapshot({
      activeBranch: "main",
      branches: { main: { name: "main", state: {}, created_at: 1 } },
    });
    const data = snap.toDict();
    expect(data.active_branch).toBe("main");
    expect("activeBranch" in data).toBe(false);
  });
});

describe("session — SessionPlugin", () => {
  it("afterAgent forks state into auto:<agent>", () => {
    const store = new SessionStore();
    const plugin = new SessionPlugin(store);
    const ctx = { state: { counter: 1 } };
    plugin.afterAgent(ctx, "writer");
    expect(store.forks.has("auto:writer")).toBe(true);
    const branch = store.forks.get("auto:writer");
    expect((branch.state as { counter: number }).counter).toBe(1);
  });

  it("beforeAgent restores a prior branch into ctx.state", () => {
    const store = new SessionStore();
    store.fork("auto:writer", { counter: 99 });
    const plugin = new SessionPlugin(store);
    const ctx: { state: Record<string, unknown> } = { state: {} };
    plugin.beforeAgent(ctx, "writer");
    expect(ctx.state.counter).toBe(99);
  });

  it("custom branchNamer overrides the default prefix", () => {
    const store = new SessionStore();
    const plugin = new SessionPlugin(store, {
      branchNamer: (name) => `snap/${name}`,
    });
    plugin.afterAgent({ state: { ok: true } }, "reviewer");
    expect(store.forks.has("snap/reviewer")).toBe(true);
  });
});

// ─── H façade smoke ────────────────────────────────────────────────────────

describe("H façade — new helpers", () => {
  it("hook helpers return structured decisions", () => {
    expect(H.hookAllow().isAllow).toBe(true);
    expect(H.hookDeny("no").action).toBe("deny");
    expect(H.hookModify({ x: 1 }).toolInput).toEqual({ x: 1 });
    expect(H.hookReplace(7).output).toBe(7);
    expect(H.hookAsk("?").prompt).toBe("?");
    expect(H.hookInject("i").systemMessage).toBe("i");
    const m = H.hookForTool(HookEvent.PreToolUse, "bash");
    expect(m.event).toBe(HookEvent.PreToolUse);
  });

  it("subagent helpers build registry + task tool", () => {
    const reg = H.subagentRegistry([
      H.subagentSpec({ role: "r", instruction: "do", description: "d" }),
    ]);
    const task = H.taskTool(reg, new FakeSubagentRunner());
    expect(task("r", "hi")).toContain("[r]");
  });

  it("fs helpers return usable backends", () => {
    const mem = H.fsMemory();
    mem.writeText("/x", "1");
    expect(mem.readText("/x")).toBe("1");

    const sandbox = new SandboxPolicy({ workspace: "/ws" });
    const sb = H.fsSandboxed(H.fsMemory(), sandbox);
    sb.writeText("/ws/a", "ok");
    expect(sb.readText("/ws/a")).toBe("ok");
    expect(() => sb.writeText("/etc/bad", "x")).toThrow(SandboxViolation);
  });
});

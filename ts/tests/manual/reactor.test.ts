/**
 * Phase F + G: Signal + SignalPredicate + Reactor + AgentToken + TokenRegistry.
 *
 * Mirrors python/tests/manual/test_reactor.py + test_agent_token.py.
 */

import { describe, expect, it } from "vitest";

import { Signal, Reactor } from "../../src/namespaces/reactor.js";
import { EventBus } from "../../src/namespaces/harness/events.js";
import { AgentToken, TokenRegistry } from "../../src/namespaces/harness/lifecycle.js";

describe("Signal — reactive state cell", () => {
  it("default_armed: get/set round-trip", () => {
    const s = new Signal("x", 0);
    expect(s.get()).toBe(0);
    s.set(5);
    expect(s.get()).toBe(5);
  });

  it("skips emission on equality guard", () => {
    const s = new Signal("x", 1);
    const log: number[] = [];
    s.subscribe((v) => log.push(v as number));
    expect(s.set(1)).toBe(false);
    expect(log).toEqual([]);
    expect(s.set(2)).toBe(true);
    expect(log).toEqual([2]);
  });

  it("force=true emits even on equality", () => {
    const s = new Signal("x", "a");
    const log: string[] = [];
    s.subscribe((v) => log.push(v as string));
    s.set("a", { force: true });
    expect(log).toEqual(["a"]);
  });

  it("version is monotonic and survives no-ops", () => {
    const s = new Signal("x", 1);
    expect(s.version).toBe(0);
    s.set(2);
    expect(s.version).toBe(1);
    s.set(2); // equal, skipped
    expect(s.version).toBe(1);
    s.set(3);
    expect(s.version).toBe(2);
  });

  it("subscribe returns unsubscribe callable", () => {
    const s = new Signal("x", 0);
    const log: number[] = [];
    const off = s.subscribe((v) => log.push(v as number));
    s.set(1);
    off();
    s.set(2);
    expect(log).toEqual([1]);
  });

  it("emits SignalChangedEvent on attached bus", () => {
    const bus = new EventBus({ maxBuffer: 10 });
    const s = new Signal("count", 0).attach(bus);
    s.set(7);
    expect(bus.history.map((e) => e.kind)).toEqual(["signal_changed"]);
    const evt = bus.history[0] as {
      kind: string;
      name: string;
      version: number;
      value: unknown;
      previous: unknown;
    };
    expect(evt.name).toBe("count");
    expect(evt.version).toBe(1);
    expect(evt.value).toBe(7);
    expect(evt.previous).toBe(0);
  });

  it("update() applies fn atomically", () => {
    const s = new Signal("x", 10);
    s.update((v) => v + 5);
    expect(s.get()).toBe(15);
  });

  it("observer isolation: one throwing subscriber does not block others", () => {
    const s = new Signal("x", 0);
    s.subscribe(() => {
      throw new Error("boom");
    });
    const log: number[] = [];
    s.subscribe((v) => log.push(v as number));
    s.set(1);
    expect(log).toEqual([1]);
  });
});

describe("SignalPredicate — composition", () => {
  it("changed fires on any mutation", () => {
    const s = new Signal("x", 0);
    const log: number[] = [];
    const reactor = new Reactor();
    reactor.when(s.changed, ({ current }) => {
      log.push(current as number);
    });
    reactor.start();
    s.set(1);
    s.set(2);
    expect(log).toEqual([1, 2]);
  });

  it("rising only fires when value increases", () => {
    const s = new Signal("x", 5);
    const log: number[] = [];
    const r = new Reactor();
    r.when(s.rising, ({ current }) => {
      log.push(current as number);
    });
    r.start();
    s.set(10); // rising
    s.set(7); // falling, skip
    s.set(12); // rising
    expect(log).toEqual([10, 12]);
  });

  it("falling only fires when value decreases", () => {
    const s = new Signal("x", 5);
    const log: number[] = [];
    const r = new Reactor();
    r.when(s.falling, ({ current }) => {
      log.push(current as number);
    });
    r.start();
    s.set(3);
    s.set(10); // rising, skip
    s.set(1);
    expect(log).toEqual([3, 1]);
  });

  it("is(value) fires only on equality", () => {
    const s = new Signal("state", "idle");
    const log: string[] = [];
    const r = new Reactor();
    r.when(s.is("ready"), ({ current }) => {
      log.push(current as string);
    });
    r.start();
    s.set("loading");
    s.set("ready");
    expect(log).toEqual(["ready"]);
  });

  it("where() adds an extra guard", () => {
    const s = new Signal("n", 0);
    const log: number[] = [];
    const r = new Reactor();
    r.when(
      s.changed.where((c) => (c as number) > 5),
      ({ current }) => {
        log.push(current as number);
      },
    );
    r.start();
    s.set(3);
    s.set(8);
    s.set(2);
    s.set(10);
    expect(log).toEqual([8, 10]);
  });

  it("and() combines two predicates", () => {
    const a = new Signal("a", 0);
    const b = new Signal("b", "init");
    const log: string[] = [];
    const r = new Reactor();
    r.when(a.changed.and(b.is("ready")), () => {
      log.push("fired");
    });
    r.start();
    a.set(1); // b != ready, skip
    b.set("ready"); // a.changed fails on this signal; but b.is("ready") is true
    // Separately: the rule only deps on both signals, so mutation of either
    // triggers evaluation; combined check requires both to pass.
    // After both mutations, trigger change on a with b=ready.
    a.set(2);
    expect(log.length).toBeGreaterThanOrEqual(1);
  });

  it("or() fires when either condition matches", () => {
    const a = new Signal("a", 0);
    const b = new Signal("b", 0);
    const log: string[] = [];
    const r = new Reactor();
    r.when(a.is(1 as unknown).or(b.is(1 as unknown)), () => log.push("hit"));
    r.start();
    a.set(1);
    b.set(1);
    expect(log.length).toBe(2);
  });

  it("not() inverts", () => {
    const s = new Signal("x", 1);
    const log: number[] = [];
    const r = new Reactor();
    r.when(s.is(0 as unknown).not(), ({ current }) => log.push(current as number));
    r.start();
    s.set(5);
    s.set(0); // should NOT fire
    s.set(3);
    expect(log).toEqual([5, 3]);
  });
});

describe("Reactor — priority + preemption", () => {
  it("higher-priority rule runs first (lower number = higher priority)", async () => {
    const s = new Signal("x", 0);
    const log: string[] = [];
    const r = new Reactor();
    // rule 1 low priority (100), rule 2 high priority (10)
    r.when(s.changed, async () => {
      log.push("low-start");
      await new Promise((res) => setTimeout(res, 10));
      log.push("low-end");
    });
    r.when(
      s.changed,
      async () => {
        log.push("high-start");
        await new Promise((res) => setTimeout(res, 5));
        log.push("high-end");
      },
      { priority: 10 },
    );
    r.start();
    s.set(1);
    await new Promise((res) => setTimeout(res, 40));
    expect(log[0]).toBe("high-start");
    expect(log).toContain("low-start");
  });

  it("preemptive rule cancels a running lower-priority rule", async () => {
    const s = new Signal("x", 0);
    let preempted = false;
    const r = new Reactor({
      onPreempt: () => {
        preempted = true;
      },
      cursor: () => 42,
    });
    // Capture the token of the first worker run so we can assert on
    // its state after preemption (a re-dispatch will swap in a new
    // token, so the registry view is not what we want here).
    const capturedTokens: AgentToken[] = [];
    r.when(
      s.changed,
      async (ctx) => {
        if (ctx.token) capturedTokens.push(ctx.token);
        for (let i = 0; i < 20; i++) {
          await new Promise((res) => setTimeout(res, 5));
          if (ctx.token?.cancelled) return;
        }
      },
      { agentName: "worker", priority: 100 },
    );
    r.when(
      s.rising,
      async () => {
        // high-prio preempts
      },
      { agentName: "interrupter", priority: 5, preemptive: true },
    );
    r.start();
    s.set(1); // worker starts
    await new Promise((res) => setTimeout(res, 10));
    s.set(5); // rising → interrupter preempts
    await new Promise((res) => setTimeout(res, 20));
    expect(preempted).toBe(true);
    expect(capturedTokens.length).toBeGreaterThanOrEqual(1);
    const firstToken = capturedTokens[0]!;
    expect(firstToken.cancelled).toBe(true);
    expect(firstToken.resumeCursor).toBe(42);
  });
});

describe("AgentToken + TokenRegistry", () => {
  it("defaults: armed, cursor 0, agentName stored", () => {
    const t = new AgentToken("writer");
    expect(t.cancelled).toBe(false);
    expect(t.agentName).toBe("writer");
    expect(t.resumeCursor).toBe(0);
  });

  it("cancelWithCursor records both", () => {
    const t = new AgentToken("w");
    t.cancelWithCursor(42);
    expect(t.cancelled).toBe(true);
    expect(t.resumeCursor).toBe(42);
  });

  it("reset clears cancellation and cursor", () => {
    const t = new AgentToken("w");
    t.cancelWithCursor(10);
    t.reset();
    expect(t.cancelled).toBe(false);
    expect(t.resumeCursor).toBe(0);
  });

  it("registry.getOrCreate is idempotent", () => {
    const reg = new TokenRegistry();
    const a = reg.getOrCreate("w");
    const b = reg.getOrCreate("w");
    expect(a).toBe(b);
  });

  it("registry.cancel returns false for unknown agent", () => {
    expect(new TokenRegistry().cancel("nobody")).toBe(false);
  });

  it("registry.cancel is targeted — siblings untouched", () => {
    const reg = new TokenRegistry();
    const w = reg.getOrCreate("writer");
    const c = reg.getOrCreate("critic");
    reg.cancel("writer", { resumeCursor: 7 });
    expect(w.cancelled).toBe(true);
    expect(w.resumeCursor).toBe(7);
    expect(c.cancelled).toBe(false);
  });

  it("resetAll clears every token", () => {
    const reg = new TokenRegistry();
    const a = reg.getOrCreate("a");
    const b = reg.getOrCreate("b");
    reg.cancel("a");
    reg.cancel("b");
    reg.resetAll();
    expect(a.cancelled).toBe(false);
    expect(b.cancelled).toBe(false);
  });

  it("has/size report registry membership", () => {
    const reg = new TokenRegistry();
    expect(reg.has("w")).toBe(false);
    expect(reg.size).toBe(0);
    reg.getOrCreate("w");
    expect(reg.has("w")).toBe(true);
    expect(reg.size).toBe(1);
  });
});

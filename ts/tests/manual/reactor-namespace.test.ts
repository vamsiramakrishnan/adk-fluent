/**
 * Tests for the R namespace + .on() integration — TypeScript parity
 * with `python/tests/manual/test_reactor_namespace.py`.
 *
 * Covers the 100x-native reactor surface: registry-backed signals,
 * name-addressed predicate factories, declarative rule attachment on
 * builders, compile-time rule walking, and the debounce/throttle
 * immutability fix.
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  Agent,
  Pipeline,
  FanOut,
  R,
  ReactorPlugin,
  Signal,
  SignalPredicate,
  SignalRegistry,
} from "../../src/index.js";
import { EventBus } from "../../src/namespaces/harness/events.js";

beforeEach(() => {
  R.clear();
});

afterEach(() => {
  R.clear();
});

describe("R — registry basics", () => {
  it("signal is idempotent: same name returns the same instance", () => {
    const a = R.signal("temp", 72);
    const b = R.signal("temp");
    expect(a).toBe(b);
    expect(a.get()).toBe(72);
  });

  it("registered signal reuses the attached bus", () => {
    const bus = new EventBus({ maxBuffer: 10 });
    R.attach(bus);
    const sig = R.signal("pressure", 1.0);
    sig.set(2.0);
    // A single signal_changed event flows through the bus.
    expect(bus.history.map((e) => e.kind)).toEqual(["signal_changed"]);
  });

  it("R.scope() returns an isolated registry", () => {
    const scoped = R.scope();
    const s1 = scoped.signal("x", 1);
    expect(R.names()).not.toContain("x");
    expect(scoped.get("x")).toBe(s1);
  });

  it("R.get() on a missing signal throws", () => {
    expect(() => R.get("nope")).toThrowError(/not registered/);
  });
});

describe("R — predicate factories", () => {
  it("R.rising(name) declares a rising predicate", () => {
    R.signal("temp", 0);
    const pred = R.rising("temp");
    expect(pred).toBeInstanceOf(SignalPredicate);
    expect(pred.deps).toHaveLength(1);
    expect(pred.deps[0]!.name).toBe("temp");
  });

  it("R.any()/R.all() compose predicate deps correctly", () => {
    R.signal("a", 0);
    R.signal("b", 0);
    const anyP = R.any(R.changed("a"), R.changed("b"));
    const names = new Set(anyP.deps.map((s) => s.name));
    expect(names).toEqual(new Set(["a", "b"]));

    const allP = R.all(R.changed("a"), R.changed("b"));
    const allNames = new Set(allP.deps.map((s) => s.name));
    expect(allNames).toEqual(new Set(["a", "b"]));
  });

  it("R.is(name, value) fires on equality match", () => {
    R.signal("mode", "idle");
    const pred = R.is("mode", "running");
    let fired = false;
    pred.evaluate("running", "idle", () => {
      fired = true;
    });
    expect(fired).toBe(true);

    let firedAgain = false;
    pred.evaluate("idle", "running", () => {
      firedAgain = true;
    });
    expect(firedAgain).toBe(false);
  });
});

describe("SignalPredicate — debounce/throttle immutability fix", () => {
  it("debounce() returns a fresh predicate, base unchanged", () => {
    R.signal("temp", 0);
    const base = R.changed("temp");
    const debounced = base.debounce(50);
    expect(debounced).not.toBe(base);
    expect(base._debounceMsValue).toBe(0);
    expect(debounced._debounceMsValue).toBe(50);
  });

  it("throttle() returns a fresh predicate, base unchanged", () => {
    R.signal("temp", 0);
    const base = R.changed("temp");
    const throttled = base.throttle(100);
    expect(throttled).not.toBe(base);
    expect(base._throttleMsValue).toBe(0);
    expect(throttled._throttleMsValue).toBe(100);
  });

  it("debounce().throttle() chains preserve both windows", () => {
    R.signal("temp", 0);
    const chained = R.changed("temp").debounce(50).throttle(100);
    expect(chained._debounceMsValue).toBe(50);
    expect(chained._throttleMsValue).toBe(100);
  });
});

describe("Builder.on()", () => {
  it("attaches a RuleSpec to the builder", () => {
    const agent = new Agent("cooler", "gemini-2.5-flash").on(
      R.rising("temp"),
      () => {},
    );
    const rules = agent._reactor_rules;
    expect(rules).toHaveLength(1);
    expect(rules[0]!.predicate.deps[0]!.name).toBe("temp");
    expect(rules[0]!.name).toBe("cooler");
  });

  it("accepts a bare Signal (promoted to .changed)", () => {
    const sig = R.signal("alert", false);
    const agent = new Agent("responder").on(sig, () => {});
    expect(agent._reactor_rules[0]!.predicate.deps[0]!.name).toBe("alert");
  });

  it("rejects non-predicate inputs with a TypeError", () => {
    const agent = new Agent("responder");
    expect(() => agent.on("not a predicate" as never, () => {})).toThrowError(
      /SignalPredicate or Signal/,
    );
  });

  it("propagates priority and preemptive options", () => {
    const agent = new Agent("x").on(R.changed("alert"), () => {}, {
      priority: 10,
      preemptive: true,
    });
    const spec = agent._reactor_rules[0]!;
    expect(spec.priority).toBe(10);
    expect(spec.preemptive).toBe(true);
  });

  it("is immutable — clone on attach", () => {
    const base = new Agent("x");
    R.signal("alert", false);
    const withRule = base.on(R.changed("alert"), () => {});
    expect(base._reactor_rules).toHaveLength(0);
    expect(withRule._reactor_rules).toHaveLength(1);
  });
});

describe("R.compile — rule discovery through composite builders", () => {
  it("walks Pipeline children", () => {
    R.signal("temp", 0);
    const inner = new Agent("cool").on(R.rising("temp"), () => {});
    const outer = new Pipeline("flow").step(inner);
    const reactor = R.compile([outer]);
    expect(reactor.getRules()).toHaveLength(1);
    expect(reactor.getRules()[0]!.predicate.deps[0]!.name).toBe("temp");
  });

  it("walks FanOut branches", () => {
    R.signal("a", 0);
    R.signal("b", 0);
    const fa = new FanOut("parallel")
      .branch(new Agent("x").on(R.changed("a"), () => {}))
      .branch(new Agent("y").on(R.changed("b"), () => {}));
    const reactor = R.compile([fa]);
    const names = new Set(
      reactor.getRules().map((rule) => rule.predicate.deps[0]!.name),
    );
    expect(names).toEqual(new Set(["a", "b"]));
  });

  it("includes standalone rules registered via R.rule()", () => {
    R.signal("x", 0);
    R.rule(R.changed("x"), () => {}, { name: "manual" });
    const reactor = R.compile();
    const names = reactor.getRules().map((rule) => rule.agentName);
    expect(names).toContain("manual");
  });
});

describe("R.compile — end-to-end rule firing", () => {
  it("rising predicate fires the handler once on cross-threshold set", async () => {
    const bus = new EventBus({ maxBuffer: 100 });
    R.attach(bus);
    const temp = R.signal("temp", 72);

    const fires: Array<[unknown, unknown]> = [];
    const handler = async (ctx: { current: unknown; previous: unknown }) => {
      fires.push([ctx.current, ctx.previous]);
    };

    const agent = new Agent("cooler", "gemini-2.5-flash").on(
      R.rising("temp").where((v, _prev) => (v as number) > 90),
      handler,
      { priority: 10 },
    );

    const reactor = R.compile([agent], { bus });
    reactor.start();

    temp.set(80); // rising but below 90 → no fire
    temp.set(95); // rising above 90 → fires
    temp.set(92); // falling → no fire

    // Give microtasks a chance to resolve any async handlers.
    await new Promise((resolve) => setTimeout(resolve, 20));

    reactor.stop();
    expect(fires).toEqual([[95, 80]]);
  });
});

describe("ReactorPlugin", () => {
  it("starts and stops the reactor from session callbacks", async () => {
    const bus = new EventBus({ maxBuffer: 100 });
    R.attach(bus);
    const sig = R.signal("ping", false);

    let fired = false;
    const agent = new Agent("listener").on(R.changed("ping"), async () => {
      fired = true;
    });

    const reactor = R.compile([agent], { bus });
    const plugin = new ReactorPlugin(reactor);

    await plugin.onSessionStart();
    sig.set(true);
    await new Promise((resolve) => setTimeout(resolve, 20));
    await plugin.onSessionEnd();
    expect(fired).toBe(true);
  });
});

describe("R — re-exports", () => {
  it("SignalRegistry and Signal are exported from the package root", () => {
    expect(SignalRegistry).toBeDefined();
    expect(Signal).toBeDefined();
  });
});

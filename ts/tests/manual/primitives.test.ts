/**
 * Tests for primitives, routing, patterns, and A2A modules.
 */

import { describe, it, expect as vexpect } from "vitest";
import { Agent } from "../../src/builders/agent.js";
import {
  tap,
  expect as fluentExpect,
  mapOver,
  gate,
  race,
  dispatch,
  join,
  Primitive,
} from "../../src/primitives/index.js";
import { Route } from "../../src/routing/index.js";
import {
  reviewLoop,
  mapReduce,
  cascade,
  fanOutMerge,
  chain,
  conditional,
  supervised,
} from "../../src/patterns/index.js";
import { RemoteAgent, A2AServer, AgentRegistry } from "../../src/a2a/index.js";

describe("primitives", () => {
  it("tap creates a Primitive with kind=tap", () => {
    const t = tap((s) => void s);
    vexpect(t).toBeInstanceOf(Primitive);
    const built = t.build();
    vexpect(built._type).toBe("Primitive");
    vexpect(built._kind).toBe("tap");
  });

  it("expect attaches a predicate and message", () => {
    const e = fluentExpect((s) => Boolean(s.ok), "ok must be true");
    const built = e.build();
    vexpect(built._kind).toBe("expect");
    vexpect(built._msg).toBe("ok must be true");
  });

  it("mapOver records the key and inner agent", () => {
    const inner = new Agent("worker");
    const m = mapOver("items", inner);
    const built = m.build();
    vexpect(built._key).toBe("items");
    vexpect(built._kind).toBe("map_over");
  });

  it("gate wraps an agent with a predicate", () => {
    const inner = new Agent("worker");
    const g = gate((s) => Boolean(s.ready), inner);
    vexpect(g.build()._kind).toBe("gate");
  });

  it("race takes multiple agents", () => {
    const r = race(new Agent("a"), new Agent("b"), new Agent("c"));
    vexpect(r.build()._kind).toBe("race");
  });

  it("dispatch records onComplete callback", () => {
    let called = false;
    const d = dispatch(new Agent("bg"), {
      onComplete: () => {
        called = true;
      },
    });
    const built = d.build();
    vexpect(built._kind).toBe("dispatch");
    vexpect(typeof built._on_complete).toBe("function");
    (built._on_complete as () => void)();
    vexpect(called).toBe(true);
  });

  it("join creates a sync barrier primitive", () => {
    const j = join();
    vexpect(j.build()._kind).toBe("join");
  });
});

describe("Route", () => {
  it("supports eq/contains/gt/otherwise", () => {
    const router = new Route("tier")
      .eq("VIP", new Agent("vip"))
      .contains("trial", new Agent("trial"))
      .gt(100, new Agent("big"))
      .otherwise(new Agent("default"));

    const built = router.build() as Record<string, unknown>;
    vexpect(built._type).toBe("Route");
    vexpect(built.key).toBe("tier");
    const branches = built.branches as Array<Record<string, unknown>>;
    vexpect(branches.length).toBe(3);
    vexpect(branches[0].label).toBe("eq:VIP");
    vexpect(branches[1].label).toBe("contains:trial");
    vexpect(branches[2].label).toBe("gt:100");
    vexpect(built.default).toBeDefined();
  });

  it("predicates evaluate against state", () => {
    const router = new Route("score")
      .gt(50, new Agent("high"))
      .otherwise(new Agent("low"));
    const built = router.build() as Record<string, unknown>;
    const branches = built.branches as Array<{ predicate: (s: Record<string, unknown>) => boolean }>;
    vexpect(branches[0].predicate({ score: 80 })).toBe(true);
    vexpect(branches[0].predicate({ score: 10 })).toBe(false);
  });
});

describe("patterns", () => {
  it("reviewLoop builds a Loop", () => {
    const w = new Agent("writer");
    const r = new Agent("reviewer");
    const loop = reviewLoop(w, r, { qualityKey: "score", target: 0.9, maxRounds: 4 });
    const built = loop.build() as Record<string, unknown>;
    vexpect(built._type).toBe("LoopAgent");
  });

  it("cascade builds a Fallback chain", () => {
    const c = cascade(new Agent("a"), new Agent("b"), new Agent("c"));
    const built = c.build() as Record<string, unknown>;
    vexpect(built._type).toBe("Fallback");
  });

  it("chain builds a Pipeline", () => {
    const ch = chain(new Agent("a"), new Agent("b"));
    const built = ch.build() as Record<string, unknown>;
    vexpect(built._type).toBe("SequentialAgent");
  });

  it("conditional with one branch returns a gate", () => {
    const cond = conditional((s) => Boolean(s.ok), new Agent("then"));
    vexpect(cond).toBeInstanceOf(Primitive);
  });

  it("conditional with else builds a Pipeline", () => {
    const cond = conditional(
      (s) => Boolean(s.ok),
      new Agent("then"),
      new Agent("else"),
    );
    const built = cond.build() as Record<string, unknown>;
    vexpect(built._type).toBe("SequentialAgent");
  });

  it("supervised builds a Loop", () => {
    const s = supervised(new Agent("worker"), new Agent("supervisor"));
    const built = s.build() as Record<string, unknown>;
    vexpect(built._type).toBe("LoopAgent");
  });

  it("mapReduce builds a Pipeline", () => {
    const mr = mapReduce(new Agent("mapper"), new Agent("reducer"));
    const built = mr.build() as Record<string, unknown>;
    vexpect(built._type).toBe("SequentialAgent");
    vexpect(built._items_key).toBe("items");
    vexpect(built._result_key).toBe("result");
  });

  it("fanOutMerge builds a FanOut", () => {
    const fo = fanOutMerge([new Agent("a"), new Agent("b")]);
    const built = fo.build() as Record<string, unknown>;
    vexpect(built._type).toBe("ParallelAgent");
    vexpect(built._merge_key).toBe("merged");
  });
});

describe("A2A", () => {
  it("RemoteAgent builds with metadata", () => {
    const r = new RemoteAgent("researcher", { agentCard: "http://x/.well-known/agent.json" })
      .describe("Remote researcher")
      .timeout(30)
      .sends("query")
      .receives("findings")
      .persistentContext();
    const built = r.build();
    vexpect(built._type).toBe("RemoteAgent");
    vexpect(built.agent_card).toBe("http://x/.well-known/agent.json");
    vexpect(built.timeout).toBe(30);
    vexpect(built.description).toBe("Remote researcher");
  });

  it("RemoteAgent.discover builds a well-known URL", () => {
    const r = RemoteAgent.discover("research.example.com");
    const built = r.build();
    vexpect(built.agent_card).toBe("https://research.example.com/.well-known/agent.json");
  });

  it("A2AServer builds with skills and provider", () => {
    const s = new A2AServer(new Agent("agent"))
      .port(8001)
      .version("1.0.0")
      .provider("Acme", "https://acme.com")
      .skill("research", "Academic Research", { tags: ["citations"] })
      .healthCheck()
      .gracefulShutdown(10);
    const built = s.build() as Record<string, unknown>;
    vexpect(built._type).toBe("A2AServer");
    vexpect(built.port).toBe(8001);
    vexpect(built.version).toBe("1.0.0");
    const skills = built.skills as Array<Record<string, unknown>>;
    vexpect(skills.length).toBe(1);
    vexpect(skills[0].id).toBe("research");
  });

  it("AgentRegistry.find returns a RemoteAgent", () => {
    const reg = new AgentRegistry("http://registry:9000");
    const r = reg.find({ name: "researcher" });
    vexpect(r).toBeInstanceOf(RemoteAgent);
  });
});

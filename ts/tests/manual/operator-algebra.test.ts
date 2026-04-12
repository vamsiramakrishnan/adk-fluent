/**
 * Tests for operator algebra (.then, .parallel, .times, .timesUntil, .fallback,
 * .outputAs) and how they compose with each other and with the workflow
 * builders. These exercise the corners of `BuilderBase` that the cookbook
 * suite touches only as a side effect.
 */
import { describe, expect, it } from "vitest";
import { Agent } from "../../src/builders/agent.js";
import { Pipeline, FanOut, Loop, Fallback } from "../../src/builders/workflow.js";
import { until } from "../../src/core/types.js";

const M = "gemini-2.5-flash";

function name(builder: { name: string }): string {
  return builder.name;
}

describe(".then() composition", () => {
  it("two agents → Pipeline with two sub_agents", () => {
    const p = new Agent("a", M).then(new Agent("b", M));
    expect(p).toBeInstanceOf(Pipeline);
    const cfg = p.inspect();
    expect(cfg["lists.sub_agents"]).toBe(2);
  });

  it("appends to an existing Pipeline (does not nest)", () => {
    const p = new Agent("a", M).then(new Agent("b", M)).then(new Agent("c", M));
    const cfg = p.inspect();
    // Three flat steps — not 2 with one nested.
    expect(cfg["lists.sub_agents"]).toBe(3);
  });

  it("accepts a plain function as a step", () => {
    const fn = (s: Record<string, unknown>) => s;
    const p = new Agent("a", M).then(fn);
    const built = p.build() as { subAgents: unknown[] };
    expect(built.subAgents.length).toBe(2);
    expect(typeof built.subAgents[1]).toBe("function");
  });

  it("naming reflects operands", () => {
    const p = new Agent("alpha").then(new Agent("beta"));
    expect(name(p)).toBe("alpha_then_beta");
  });
});

describe(".parallel() composition", () => {
  it("two agents → FanOut with two branches", () => {
    const f = new Agent("a", M).parallel(new Agent("b", M));
    expect(f).toBeInstanceOf(FanOut);
    expect(f.inspect()["lists.sub_agents"]).toBe(2);
  });

  it("flat-chains additional branches", () => {
    const f = new Agent("a", M).parallel(new Agent("b", M)).parallel(new Agent("c", M));
    expect(f.inspect()["lists.sub_agents"]).toBe(3);
  });

  it("naming uses _and_ separator", () => {
    const f = new Agent("alpha").parallel(new Agent("beta"));
    expect(name(f)).toBe("alpha_and_beta");
  });
});

describe(".times() composition", () => {
  it("rejects iterations < 1", () => {
    expect(() => new Agent("a").times(0)).toThrow();
    expect(() => new Agent("a").times(-2)).toThrow();
  });

  it("wraps a single agent in a Loop body of one", () => {
    const loop = new Agent("a").times(3);
    expect(loop).toBeInstanceOf(Loop);
    expect(loop.inspect().max_iterations).toBe(3);
    expect(loop.inspect()["lists.sub_agents"]).toBe(1);
  });

  it("flattens a Pipeline into the loop body", () => {
    const loop = new Agent("a").then(new Agent("b")).times(5);
    expect(loop.inspect().max_iterations).toBe(5);
    // Loop body should have both pipeline steps, not the wrapping pipeline.
    expect(loop.inspect()["lists.sub_agents"]).toBe(2);
  });
});

describe(".timesUntil() composition", () => {
  it("accepts a bare predicate + max", () => {
    const pred = (s: Record<string, unknown>) => s["done"] === true;
    const loop = new Agent("a").timesUntil(pred, { max: 7 });
    expect(loop.inspect().max_iterations).toBe(7);
    expect(loop.inspect()._until_predicate).toBe(pred);
  });

  it("accepts an UntilSpec object via the until() helper", () => {
    const spec = until((s) => Boolean(s["done"]), 4);
    const loop = new Agent("a").timesUntil(spec);
    expect(loop.inspect().max_iterations).toBe(4);
    expect(typeof loop.inspect()._until_predicate).toBe("function");
  });

  it("defaults max to 10 when omitted", () => {
    const loop = new Agent("a").timesUntil(() => true);
    expect(loop.inspect().max_iterations).toBe(10);
  });
});

describe(".fallback() composition", () => {
  it("two agents → Fallback with two children", () => {
    const fb = new Agent("fast").fallback(new Agent("strong"));
    expect(fb).toBeInstanceOf(Fallback);
    const built = fb.build() as { children: unknown[] };
    expect(built.children.length).toBe(2);
  });

  it("naming uses _or_ separator", () => {
    const fb = new Agent("primary").fallback(new Agent("backup"));
    expect(name(fb)).toBe("primary_or_backup");
  });
});

describe(".outputAs() — structured output", () => {
  it("stores schema as private _output_schema (excluded from build)", () => {
    const Schema = { type: "object" };
    const a = new Agent("parser", M).outputAs(Schema);
    expect(a.inspect()._output_schema).toBe(Schema);
    const built = a.build() as Record<string, unknown>;
    expect(built._output_schema).toBeUndefined();
  });
});

describe("immutability across operators", () => {
  it(".then() does not mutate the receiver", () => {
    const a = new Agent("a", M);
    const aCfg = a.inspect();
    a.then(new Agent("b"));
    // Original Agent must remain a single Agent (no sub_agents added).
    expect(a.inspect()).toEqual(aCfg);
  });

  it(".outputAs() returns a new builder", () => {
    const a = new Agent("a", M);
    const b = a.outputAs({ type: "object" });
    expect(a).not.toBe(b);
    expect(a.inspect()._output_schema).toBeUndefined();
    expect(b.inspect()._output_schema).toBeDefined();
  });

  it(".then() chains can be reused as sub-expressions", () => {
    const reviewers = new Agent("style").parallel(new Agent("security"));
    // Reusing in two different places must yield independent pipelines.
    const p1 = new Agent("parse").then(reviewers).then(new Agent("publish"));
    const p2 = new Agent("parse").then(reviewers).then(new Agent("ship"));
    const c1 = p1.build() as { subAgents: { name: string }[] };
    const c2 = p2.build() as { subAgents: { name: string }[] };
    expect(c1.subAgents[2].name).toBe("publish");
    expect(c2.subAgents[2].name).toBe("ship");
  });
});

describe("nested workflow builds", () => {
  it("Pipeline of FanOut of Loop of Agent flattens correctly", () => {
    const inner = new Loop("polish").step(new Agent("writer", M)).maxIterations(2);
    const fan = new FanOut("split").branch(inner).branch(new Agent("alt", M));
    const top = new Pipeline("top").step(fan).step(new Agent("final", M)).build() as {
      _type: string;
      subAgents: Array<{ _type: string; subAgents?: unknown[] }>;
    };
    expect(top._type).toBe("SequentialAgent");
    expect(top.subAgents[0]._type).toBe("ParallelAgent");
    expect(top.subAgents[0].subAgents?.length).toBe(2);
    expect((top.subAgents[0].subAgents?.[0] as { _type: string })._type).toBe("LoopAgent");
    expect(top.subAgents[1]._type).toBe("LlmAgent");
  });

  it("Fallback inside Pipeline builds with children", () => {
    const fb = new Agent("primary").fallback(new Agent("backup"));
    const p = new Pipeline("top").step(new Agent("setup")).step(fb).build() as {
      subAgents: Array<{ _type: string; children?: unknown[] }>;
    };
    expect(p.subAgents[1]._type).toBe("Fallback");
    expect(p.subAgents[1].children?.length).toBe(2);
  });
});

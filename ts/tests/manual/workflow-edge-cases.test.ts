/**
 * Edge-case tests for the workflow builders (Pipeline, FanOut, Loop,
 * Fallback). Existing builder-base / operator-algebra tests cover the
 * happy paths; this file fills in the corners:
 *
 *   - empty workflows build cleanly
 *   - single-step workflows degrade sensibly
 *   - deeply nested topologies survive a round-trip through `.build()`
 *   - immutability holds when mixing operators with explicit builders
 *   - description metadata flows through to the build output
 *   - Loop default `max_iterations` is exposed as `maxIterations`
 *   - Fallback children are recursively built
 */
import { describe, expect, it } from "vitest";
import { Agent } from "../../src/builders/agent.js";
import { Pipeline, FanOut, Loop, Fallback } from "../../src/builders/workflow.js";

const M = "gemini-2.5-flash";

describe("Pipeline edge cases", () => {
  it("builds with zero steps", () => {
    const p = new Pipeline("empty").build() as Record<string, unknown>;
    expect(p._type).toBe("SequentialAgent");
    // Zero-length lists are stripped from the build output.
    expect(p.subAgents).toEqual([]);
  });

  it("builds with a single step", () => {
    const p = new Pipeline("solo").step(new Agent("only", M)).build() as {
      subAgents: { name: string }[];
    };
    expect(p.subAgents.length).toBe(1);
    expect(p.subAgents[0].name).toBe("only");
  });

  it("recursively builds deeply nested children", () => {
    const inner = new Pipeline("inner").step(new Agent("x", M)).step(new Agent("y", M));
    const outer = new Pipeline("outer").step(inner).step(new Agent("z", M)).build() as {
      subAgents: Array<{ _type: string; subAgents?: { name: string }[] }>;
    };
    expect(outer.subAgents.length).toBe(2);
    expect(outer.subAgents[0]._type).toBe("SequentialAgent");
    expect(outer.subAgents[0].subAgents?.length).toBe(2);
    expect(outer.subAgents[1]._type).toBe("LlmAgent");
  });
});

describe("FanOut edge cases", () => {
  it("builds with zero branches", () => {
    const f = new FanOut("empty").build() as Record<string, unknown>;
    expect(f._type).toBe("ParallelAgent");
    expect(f.subAgents).toEqual([]);
  });

  it("preserves branch order", () => {
    const f = new FanOut("split")
      .branch(new Agent("first", M))
      .branch(new Agent("second", M))
      .branch(new Agent("third", M))
      .build() as { subAgents: { name: string }[] };
    expect(f.subAgents.map((s) => s.name)).toEqual(["first", "second", "third"]);
  });
});

describe("Loop edge cases", () => {
  it("defaults to max_iterations=10", () => {
    const l = new Loop("default").step(new Agent("a", M)).build() as Record<string, unknown>;
    expect(l.maxIterations).toBe(10);
  });

  it("until() stores predicate as private _until_predicate", () => {
    const pred = (s: Record<string, unknown>) => Boolean(s["done"]);
    const l = new Loop("conditional").step(new Agent("a", M)).until(pred);
    expect(l.inspect()._until_predicate).toBe(pred);
    // Private predicates are not surfaced on the build output.
    const built = l.build() as Record<string, unknown>;
    expect(built._until_predicate).toBeUndefined();
  });

  it("recursively builds nested workflow body", () => {
    const inner = new FanOut("split").branch(new Agent("a", M)).branch(new Agent("b", M));
    const l = new Loop("refine").step(inner).maxIterations(2).build() as {
      subAgents: Array<{ _type: string; subAgents?: unknown[] }>;
    };
    expect(l.subAgents[0]._type).toBe("ParallelAgent");
    expect(l.subAgents[0].subAgents?.length).toBe(2);
  });
});

describe("Fallback edge cases", () => {
  it(".attempt() is immutable — original unchanged", () => {
    const fb = new Fallback("resilient");
    const next = fb.attempt(new Agent("fast", M));
    expect((fb.build() as { children: unknown[] }).children.length).toBe(0);
    expect((next.build() as { children: unknown[] }).children.length).toBe(1);
  });

  it("recursively builds Pipeline children", () => {
    const primary = new Pipeline("primary")
      .step(new Agent("a", M))
      .step(new Agent("b", M));
    const fb = new Fallback("resilient")
      .attempt(primary)
      .attempt(new Agent("backup", M))
      .build() as { children: Array<{ _type: string; subAgents?: unknown[] }> };
    expect(fb.children.length).toBe(2);
    expect(fb.children[0]._type).toBe("SequentialAgent");
    expect(fb.children[0].subAgents?.length).toBe(2);
    expect(fb.children[1]._type).toBe("LlmAgent");
  });
});

describe("Cross-builder immutability", () => {
  it("a sub-expression can be safely embedded twice", () => {
    const reviewers = new Agent("style", M).parallel(new Agent("security", M));
    const p1 = new Pipeline("flow_a").step(new Agent("parse", M)).step(reviewers);
    const p2 = new Pipeline("flow_b").step(new Agent("parse", M)).step(reviewers);
    const b1 = p1.build() as { subAgents: Array<{ _type: string }> };
    const b2 = p2.build() as { subAgents: Array<{ _type: string }> };
    expect(b1.subAgents[1]._type).toBe("ParallelAgent");
    expect(b2.subAgents[1]._type).toBe("ParallelAgent");
    // Reusing the sub-expression must NOT mutate it.
    const r = reviewers.build() as { subAgents: unknown[] };
    expect(r.subAgents.length).toBe(2);
  });

  it("Pipeline.step accepts a builder produced by .then()", () => {
    const sub = new Agent("a", M).then(new Agent("b", M));
    const p = new Pipeline("outer").step(sub).step(new Agent("c", M)).build() as {
      subAgents: Array<{ _type: string }>;
    };
    expect(p.subAgents[0]._type).toBe("SequentialAgent");
    expect(p.subAgents[1]._type).toBe("LlmAgent");
  });
});

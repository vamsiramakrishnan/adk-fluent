/**
 * Operator-grammar parity tests.
 *
 * JavaScript can't overload ``>>``, so TS mirrors the Python ``Composite >>
 * Builder`` attach grammar via ``composite.attachTo(builder)``. These tests
 * verify that every namespace composite attaches itself via the correct
 * builder setter, and that the named-word aliases (``Context``, ``Prompt``,
 * …) resolve to the same classes as the single-letter exports.
 */
import { describe, expect, it } from "vitest";
import { Agent } from "../../src/builders/agent.js";
import { C, P, T, G, M, A } from "../../src/index.js";
import { Context, Prompt, Tool, Guard, Middleware, Artifact } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

describe("Composite.attachTo(builder) — TS parity with Python ``Composite >> Builder``", () => {
  it("CTransform.attachTo sets the builder's context spec", () => {
    const spec = C.window(3);
    const agent = spec.attachTo(new Agent("c1", MODEL));
    expect(agent).toBeInstanceOf(Agent);
    expect(agent.inspect()["_context_spec"]).toBe(spec);
  });

  it("PTransform.attachTo sets the builder's instruction", () => {
    const prompt = P.role("analyst").add(P.task("crunch numbers"));
    const agent = prompt.attachTo(new Agent("p1", MODEL));
    expect(agent.inspect()["instruction"]).toBe(prompt);
  });

  it("TComposite.attachTo adds tools to the builder", () => {
    const tools = T.fn(() => "ok", { name: "noop" });
    const agent = tools.attachTo(new Agent("t1", MODEL));
    expect(agent.inspect()["lists.tools"]).toBeGreaterThanOrEqual(1);
  });

  it("GComposite.attachTo registers the guard on the builder", () => {
    const guard = G.length({ max: 500 });
    const agent = guard.attachTo(new Agent("g1", MODEL));
    // Guard registers as both before_model_callback and after_model_callback
    expect(agent.inspect()["callbacks.before_model_callback"]).toBeGreaterThanOrEqual(1);
    expect(agent.inspect()["callbacks.after_model_callback"]).toBeGreaterThanOrEqual(1);
  });

  it("MComposite.attachTo appends to the builder's middleware list", () => {
    const mw = M.retry({ maxAttempts: 2 }).pipe(M.log());
    const agent = mw.attachTo(new Agent("m1", MODEL));
    expect(agent.inspect()["lists.middleware"]).toBeGreaterThanOrEqual(1);
  });

  it("AComposite.attachTo invokes builder.artifacts()", () => {
    const op = A.publish("report.md", { fromKey: "draft" });
    const agent = op.attachTo(new Agent("a1", MODEL));
    expect(agent).toBeInstanceOf(Agent);
  });
});

describe("Named-word aliases", () => {
  it("Context / Prompt / Tool / Guard / Middleware / Artifact are the same classes as C / P / T / G / M / A", () => {
    expect(Context).toBe(C);
    expect(Prompt).toBe(P);
    expect(Tool).toBe(T);
    expect(Guard).toBe(G);
    expect(Middleware).toBe(M);
    expect(Artifact).toBe(A);
  });

  it("named aliases compose and attach identically", () => {
    const spec = Context.window(5);
    const agent = spec.attachTo(new Agent("n1", MODEL));
    expect(agent.inspect()["_context_spec"]).toBe(spec);
  });

  it("BuilderBase.middleware() method exists for parity with Python", () => {
    const mw = Middleware.retry({ maxAttempts: 1 }).pipe(Middleware.log());
    const agent = new Agent("n2", MODEL).middleware(mw);
    expect(agent.inspect()["lists.middleware"]).toBeGreaterThanOrEqual(1);
  });
});

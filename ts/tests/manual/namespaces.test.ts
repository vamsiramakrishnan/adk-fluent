/**
 * Tests for namespace modules (S, C, P, T, G, M).
 */
import { describe, expect, it } from "vitest";
import { S } from "../../src/namespaces/state.js";
import { P } from "../../src/namespaces/prompt.js";
import { C } from "../../src/namespaces/context.js";
import { G, GuardViolation } from "../../src/namespaces/guards.js";

describe("S (State transforms)", () => {
  it("S.pick() keeps only named keys", () => {
    const transform = S.pick("a", "b");
    const result = transform.apply({ a: 1, b: 2, c: 3 });
    expect(result).toEqual({ a: 1, b: 2 });
  });

  it("S.drop() removes named keys", () => {
    const transform = S.drop("c");
    const result = transform.apply({ a: 1, b: 2, c: 3 });
    expect(result).toEqual({ a: 1, b: 2 });
  });

  it("S.rename() renames keys", () => {
    const transform = S.rename({ old_name: "new_name" });
    const result = transform.apply({ old_name: "value", other: 42 });
    expect(result).toEqual({ new_name: "value", other: 42 });
  });

  it("S.set() sets explicit values", () => {
    const transform = S.set({ x: 10, y: 20 });
    const result = transform.apply({ a: 1 });
    expect(result).toEqual({ a: 1, x: 10, y: 20 });
  });

  it("S.default_() fills missing keys", () => {
    const transform = S.default_({ a: 0, b: 0 });
    const result = transform.apply({ a: 1 });
    expect(result).toEqual({ a: 1, b: 0 });
  });

  it("S.transform() applies function to key", () => {
    const transform = S.transform("count", (v) => (v as number) + 1);
    const result = transform.apply({ count: 5 });
    expect(result).toEqual({ count: 6 });
  });

  it("S.require() throws on missing keys", () => {
    const transform = S.require("needed");
    expect(() => transform.apply({})).toThrow('Required state key "needed" is missing');
    expect(() => transform.apply({ needed: "here" })).not.toThrow();
  });

  it("S.guard() throws on failed predicate", () => {
    const transform = S.guard((s) => (s.count as number) > 0, "Count must be positive");
    expect(() => transform.apply({ count: 0 })).toThrow("Count must be positive");
    expect(() => transform.apply({ count: 1 })).not.toThrow();
  });

  it("pipe() chains transforms", () => {
    const transform = S.set({ x: 10 }).pipe(S.transform("x", (v) => (v as number) * 2));
    const result = transform.apply({});
    expect(result).toEqual({ x: 20 });
  });

  it("when() applies conditionally", () => {
    const transform = S.when((s) => (s.flag as boolean) === true, S.set({ bonus: "yes" }));
    expect(transform.apply({ flag: true })).toEqual({ flag: true, bonus: "yes" });
    expect(transform.apply({ flag: false })).toEqual({ flag: false });
  });
});

describe("P (Prompt composition)", () => {
  it("P.role() creates a role section", () => {
    const prompt = P.role("Senior analyst");
    expect(prompt.render()).toContain("## Role");
    expect(prompt.render()).toContain("Senior analyst");
  });

  it("P.task() creates a task section", () => {
    const prompt = P.task("Analyze the data");
    expect(prompt.render()).toContain("## Task");
  });

  it("P.constraint() creates constraint bullets", () => {
    const prompt = P.constraint("Be concise", "Use tables");
    expect(prompt.render()).toContain("- Be concise");
    expect(prompt.render()).toContain("- Use tables");
  });

  it(".add() composes multiple sections", () => {
    const prompt = P.role("Analyst").add(P.task("Analyze data")).add(P.constraint("Be brief"));

    const rendered = prompt.render();
    expect(rendered).toContain("## Role");
    expect(rendered).toContain("## Task");
    expect(rendered).toContain("## Constraints");
  });

  it("toString() renders the prompt", () => {
    const prompt = P.role("Helper");
    expect(`${prompt}`).toContain("Helper");
  });
});

describe("C (Context engineering)", () => {
  it("C.none() suppresses history", () => {
    const ctx = C.none();
    expect(ctx.suppressHistory).toBe(true);
  });

  it("C.default_() keeps history", () => {
    const ctx = C.default_();
    expect(ctx.suppressHistory).toBe(false);
  });

  it("C.window() suppresses with window config", () => {
    const ctx = C.window(5);
    expect(ctx.suppressHistory).toBe(true);
    expect(ctx.config.window).toBe(5);
  });

  it("C.fromState() is neutral (keeps history)", () => {
    const ctx = C.fromState("key1", "key2");
    expect(ctx.suppressHistory).toBe(false);
    expect(ctx.config.stateKeys).toEqual(["key1", "key2"]);
  });

  it(".inject() composes transforms, suppression wins", () => {
    const ctx = C.none().inject(C.fromState("data"));
    expect(ctx.suppressHistory).toBe(true);
    expect(ctx.config.stateKeys).toEqual(["data"]);
  });
});

describe("G (Guards)", () => {
  it("G.json() validates JSON output", () => {
    const guard = G.json();
    expect(guard.guards.length).toBe(1);
    // Valid JSON
    expect(() => guard.guards[0].check('{"key": "value"}')).not.toThrow();
    // Invalid JSON
    expect(() => guard.guards[0].check("not json")).toThrow(GuardViolation);
  });

  it("G.length() enforces min/max", () => {
    const guard = G.length({ min: 5, max: 10 });
    expect(() => guard.guards[0].check("hi")).toThrow(GuardViolation);
    expect(() => guard.guards[0].check("hello!")).not.toThrow();
    expect(() => guard.guards[0].check("this is way too long")).toThrow(GuardViolation);
  });

  it("guards compose with .pipe()", () => {
    const combined = G.json().pipe(G.length({ max: 1000 }));
    expect(combined.guards.length).toBe(2);
  });
});

/**
 * Tests for eval regression-gating (parity with Python CapabilitY #6) and
 * EvalSuite.add() immutability (#16).
 *
 * Synthetic EvalReports only — no LLM calls.
 */
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import { E, EvalReport, EvalSuite, RegressionError } from "../../src/namespaces/eval.js";

/** Build a synthetic report with the given metric scores. */
function report(scores: Record<string, number>): EvalReport {
  const passed = Object.values(scores).every((s) => s >= 0.5);
  return new EvalReport(passed, scores, []);
}

describe("EvalReport regression gating", () => {
  const tmpFiles: string[] = [];

  afterEach(() => {
    for (const f of tmpFiles.splice(0)) {
      try {
        fs.rmSync(f);
      } catch {
        /* ignore */
      }
    }
  });

  it("identical scores → no regression", () => {
    const base = report({ accuracy: 0.9, safety: 1.0 });
    const candidate = report({ accuracy: 0.9, safety: 1.0 });
    const result = candidate.compareToBaseline(base);
    expect(result.ok).toBe(true);
    expect(result.regressions).toHaveLength(0);
  });

  it("a dropped metric beyond tolerance → regression (ok false / throws)", () => {
    const base = report({ accuracy: 0.9 });
    const candidate = report({ accuracy: 0.7 });
    const result = candidate.compareToBaseline(base, { tolerance: 0.05 });
    expect(result.ok).toBe(false);
    expect(result.regressions.map((d) => d.metric)).toEqual(["accuracy"]);
    expect(result.deltaFor("accuracy")?.regressed).toBe(true);
    expect(() => candidate.assertNoRegression(base, { tolerance: 0.05 })).toThrow(RegressionError);
  });

  it("assertNoRegression carries the result on the error", () => {
    const base = report({ accuracy: 0.9 });
    const candidate = report({ accuracy: 0.5 });
    try {
      candidate.assertNoRegression(base);
      throw new Error("expected RegressionError");
    } catch (err) {
      expect(err).toBeInstanceOf(RegressionError);
      expect((err as RegressionError).result.ok).toBe(false);
    }
  });

  it("within tolerance → passes", () => {
    const base = report({ accuracy: 0.9 });
    const candidate = report({ accuracy: 0.88 });
    const result = candidate.compareToBaseline(base, { tolerance: 0.05 });
    expect(result.ok).toBe(true);
  });

  it("exact-tolerance boundary → passes (epsilon)", () => {
    const base = report({ accuracy: 0.9 });
    const candidate = report({ accuracy: 0.8 });
    const result = candidate.compareToBaseline(base, { tolerance: 0.1 });
    expect(result.ok).toBe(true);
    expect(result.deltaFor("accuracy")?.regressed).toBe(false);
  });

  it("improved metric → passes", () => {
    const base = report({ accuracy: 0.7 });
    const candidate = report({ accuracy: 0.95 });
    const result = candidate.compareToBaseline(base);
    expect(result.ok).toBe(true);
    expect(result.improvements.map((d) => d.metric)).toEqual(["accuracy"]);
    expect(result.deltaFor("accuracy")?.improved).toBe(true);
  });

  it("new metric never regresses", () => {
    const base = report({ accuracy: 0.9 });
    const candidate = report({ accuracy: 0.9, brand_new: 0.6 });
    const result = candidate.compareToBaseline(base);
    expect(result.ok).toBe(true);
    expect(result.deltaFor("brand_new")?.isNew).toBe(true);
    expect(result.deltaFor("brand_new")?.regressed).toBe(false);
  });

  it("missing baseline metric → regression", () => {
    const base = report({ accuracy: 0.9, coverage: 0.8 });
    const candidate = report({ accuracy: 0.9 });
    const result = candidate.compareToBaseline(base);
    expect(result.ok).toBe(false);
    expect(result.deltaFor("coverage")?.isMissing).toBe(true);
    expect(result.regressions.map((d) => d.metric)).toEqual(["coverage"]);
  });

  it("toDict/fromDict round-trips metric data", () => {
    const original = report({ accuracy: 0.9, safety: 1.0 });
    const restored = EvalReport.fromDict(original.toDict());
    expect(restored.scores).toEqual(original.scores);
    // A re-gate of an unchanged restored report should be clean.
    expect(report({ accuracy: 0.9, safety: 1.0 }).compareToBaseline(restored).ok).toBe(true);
  });

  it("saveBaseline/loadBaseline round-trips and re-gates clean", () => {
    const file = path.join(os.tmpdir(), `eval-baseline-${Date.now()}.json`);
    tmpFiles.push(file);
    const saved = report({ accuracy: 0.9, safety: 1.0 });
    saved.saveBaseline(file);
    expect(fs.existsSync(file)).toBe(true);

    // Accept a path string directly as the baseline.
    const candidate = report({ accuracy: 0.9, safety: 1.0 });
    expect(candidate.compareToBaseline(file).ok).toBe(true);

    const loaded = EvalReport.loadBaseline(file);
    expect(loaded.scores).toEqual(saved.scores);
  });

  it("accepts a toDict payload as baseline", () => {
    const base = report({ accuracy: 0.9 });
    const candidate = report({ accuracy: 0.6 });
    const result = candidate.compareToBaseline(base.toDict());
    expect(result.ok).toBe(false);
  });

  it("negative tolerance throws", () => {
    const base = report({ accuracy: 0.9 });
    expect(() => report({ accuracy: 0.9 }).compareToBaseline(base, { tolerance: -0.1 })).toThrow();
  });
});

describe("EvalSuite.add() immutability (#16)", () => {
  it("returns a new instance and leaves the original unchanged", () => {
    const original = E.suite({ name: "agent" });
    const withCase = original.add(E.case_("hello"));

    expect(withCase).not.toBe(original);
    expect(withCase).toBeInstanceOf(EvalSuite);
    expect(original.cases).toHaveLength(0);
    expect(withCase.cases).toHaveLength(1);
    // Original array identity preserved (not mutated in place).
    expect(withCase.cases).not.toBe(original.cases);
  });

  it("withCriteria() is also immutable", () => {
    const original = E.suite({ name: "agent" });
    const withCrit = original.withCriteria(E.responseMatch());
    expect(withCrit).not.toBe(original);
    expect(original.criteria).toHaveLength(0);
    expect(withCrit.criteria).toHaveLength(1);
  });
});

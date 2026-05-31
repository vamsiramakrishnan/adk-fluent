/**
 * Tests for cost-aware routing (Route.byCost / CostRoute).
 *
 * Mirrors Python's `Route.by_cost`, `CostRoute.cheapest`, and
 * `CostRoute.costliest` in `python/src/adk_fluent/_routing.py`.
 */
import { describe, expect, it } from "vitest";
import { Agent } from "../../src/builders/agent.js";
import { Route, CostRoute } from "../../src/routing/index.js";
import { CostTable } from "../../src/namespaces/harness/usage.js";

const FLASH = "gemini-2.5-flash";
const PRO = "gemini-2.5-pro";

function table(): CostTable {
  return new CostTable([
    [FLASH, { inputPerMillion: 0.3, outputPerMillion: 2.5 }],
    [PRO, { inputPerMillion: 1.25, outputPerMillion: 10.0 }],
  ]);
}

describe("Route.byCost", () => {
  it("returns a CostRoute", () => {
    expect(Route.byCost(table())).toBeInstanceOf(CostRoute);
    expect(Route.byCost()).toBeInstanceOf(CostRoute);
  });

  it("cheapest selects the lower-cost model", () => {
    const flash = new Agent("flash", FLASH);
    const pro = new Agent("pro", PRO);
    const chosen = Route.byCost(table()).cheapest(pro, flash);
    expect(chosen).toBe(flash);
  });

  it("cheapest is order-independent", () => {
    const flash = new Agent("flash", FLASH);
    const pro = new Agent("pro", PRO);
    expect(Route.byCost(table()).cheapest(flash, pro)).toBe(flash);
    expect(Route.byCost(table()).cheapest(pro, flash)).toBe(flash);
  });

  it("does not auto-choose an unknown model when a known cheaper one exists", () => {
    const flash = new Agent("flash", FLASH);
    const mystery = new Agent("mystery", "some-unlisted-model");
    const chosen = Route.byCost(table()).cheapest(mystery, flash);
    expect(chosen).toBe(flash);
  });

  it("costliest picks the higher-cost model", () => {
    const flash = new Agent("flash", FLASH);
    const pro = new Agent("pro", PRO);
    expect(Route.byCost(table()).costliest(flash, pro)).toBe(pro);
    expect(Route.byCost(table()).costliest(pro, flash)).toBe(pro);
  });

  it("costliest skips unknown (+inf) models in favour of the highest known", () => {
    const flash = new Agent("flash", FLASH);
    const mystery = new Agent("mystery", "some-unlisted-model");
    // mystery is +inf, but unknown is skipped, so the known model wins.
    expect(Route.byCost(table()).costliest(mystery, flash)).toBe(flash);
  });

  it("falls back to the first candidate when every model is unknown", () => {
    const a = new Agent("a", "unknown-a");
    const b = new Agent("b", "unknown-b");
    expect(Route.byCost(table()).cheapest(a, b)).toBe(a);
    expect(Route.byCost(table()).costliest(a, b)).toBe(a);
  });

  it("with no costTable, all models are +inf -> first candidate", () => {
    const flash = new Agent("flash", FLASH);
    const pro = new Agent("pro", PRO);
    expect(Route.byCost().cheapest(pro, flash)).toBe(pro);
    expect(Route.byCost().costliest(pro, flash)).toBe(pro);
  });

  it("a flat cost table treats every model as known", () => {
    const flat = CostTable.flat(1.0, 1.0);
    const flash = new Agent("flash", FLASH);
    const mystery = new Agent("mystery", "some-unlisted-model");
    // Both finite (equal) under a flat table -> ties break to the first.
    expect(Route.byCost(flat).cheapest(mystery, flash)).toBe(mystery);
    expect(Route.byCost(flat).costliest(mystery, flash)).toBe(mystery);
  });

  it("reads the model from a built/native agent's .model property", () => {
    const flash = { model: FLASH };
    const pro = { model: PRO };
    expect(Route.byCost(table()).cheapest(pro, flash)).toBe(flash);
  });

  it("throws when no candidates are supplied", () => {
    expect(() => Route.byCost(table()).cheapest()).toThrow();
    expect(() => Route.byCost(table()).costliest()).toThrow();
  });
});

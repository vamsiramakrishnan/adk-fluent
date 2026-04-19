/**
 * W1 — flux DSL invariants.
 *
 * Why this file lives under ``ts/tests/flux/`` (and not
 * ``catalog/flux/dsl/``):
 *   ``ts/vitest.config.ts`` restricts collection to
 *   ``include: ["tests/**\/*.test.ts"]``. A test placed in
 *   ``catalog/flux/dsl/`` is outside that include glob and never runs
 *   under ``pnpm --filter ts vitest run`` (or the npm equivalent used
 *   by this workspace). Placing the file here is the least-invasive
 *   choice — we do not touch vitest.config.ts so W2's codegen work
 *   inherits a stable test surface.
 *
 * The DSL module lives at ``catalog/flux/dsl/types.ts``, imported
 * here via a relative path. This test exercises ``defineComponent``'s
 * four invariants (name prefix, interactive-a11y, non-empty examples,
 * defaultVariants reference) plus a happy-case round-trip through
 * the Button reference spec.
 */
import { describe, expect, it } from "vitest";
import { defineComponent, z } from "../../../catalog/flux/dsl/types.js";
import type { ComponentSpec } from "../../../catalog/flux/dsl/types.js";

// ---------------------------------------------------------------------------
// Minimal valid spec factory — each test mutates one field to drive a failure.
// ---------------------------------------------------------------------------

function makeBaseSpec(overrides: Partial<ComponentSpec> = {}): ComponentSpec {
  const base: ComponentSpec = {
    name: "FluxProbe",
    extends: "Button",
    category: "primitive",
    schema: z.object({ component: z.literal("FluxProbe"), id: z.string() }),
    tokens: ["color.primary.solid"],
    variants: {
      tone: {
        primary: { backgroundColor: "$color.primary.solid" },
        neutral: { backgroundColor: "$color.bg.subtle" },
      },
    },
    defaultVariants: { tone: "primary" },
    accessibility: { label: "required" },
    llm: {
      description: "A test component.",
      examples: [{ code: "UI.probe()", caption: "smoke" }],
      budget: { children: 0, siblings: 0 },
    },
    renderer: {
      react: "./FluxProbe.tsx",
      fallback: { component: "Button" },
    },
  };
  return { ...base, ...overrides } as ComponentSpec;
}

describe("defineComponent invariants", () => {
  it("rejects a name without the 'Flux' prefix", () => {
    expect(() =>
      defineComponent(
        makeBaseSpec({ name: "Button" }),
      ),
    ).toThrowError(/must start with "Flux"/);
  });

  it("rejects an interactive extend with accessibility.label !== 'required'", () => {
    // Button is in the interactive list; 'optional' must be rejected.
    expect(() =>
      defineComponent(
        makeBaseSpec({
          name: "FluxProbeButton",
          extends: "Button",
          accessibility: { label: "optional" },
        }),
      ),
    ).toThrowError(/accessibility\.label must be "required"/);
  });

  it("rejects an empty llm.examples array", () => {
    expect(() =>
      defineComponent(
        makeBaseSpec({
          llm: {
            description: "empty examples",
            examples: [],
            budget: { children: 0, siblings: 0 },
          },
        }),
      ),
    ).toThrowError(/llm\.examples must have at least 1 entry/);
  });

  it("rejects defaultVariants.<dim> that references an undeclared variant value", () => {
    expect(() =>
      defineComponent(
        makeBaseSpec({
          defaultVariants: { tone: "bogus" },
        }),
      ),
    ).toThrowError(/defaultVariants\.tone='bogus' is not a declared variant/);
  });
});

describe("defineComponent happy path", () => {
  it("imports specs/Button.spec.ts without throwing", async () => {
    // Dynamic import so the invariant failures above cannot short-circuit this
    // test if someone breaks defineComponent's signature.
    const mod = await import("../../../catalog/flux/specs/Button.spec.ts");
    const spec = mod.default;
    expect(spec, "Button.spec.ts must export a ComponentSpec as default").toBeDefined();
    expect(spec.name).toBe("FluxButton");
    expect(spec.extends).toBe("Button");
    expect(spec.accessibility.label).toBe("required");
    expect(spec.llm.examples.length).toBeGreaterThan(0);
  });
});

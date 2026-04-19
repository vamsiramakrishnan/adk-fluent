/**
 * W4 — Fluent TS integration tests for the flux catalog.
 *
 * Mirrors ``python/tests/ui/test_flux_integration.py`` with a TypeScript
 * surface. Covers the four contract points the brief calls out:
 *
 *   1. Default catalog is ``"basic"``; outside ``UI.withCatalog`` the
 *      familiar ``UI.button`` shape stays intact.
 *   2. ``UI.withCatalog("flux", () => ...)`` flips factory dispatch so
 *      ``UI.button`` emits a ``FluxButton`` component; every overloaded
 *      factory has a flux counterpart.
 *   3. Unknown catalogs throw ``A2UIError``.
 *   4. ``UI.theme("flux-dark")`` attaches to ``UISurface.theme`` and
 *      ``T.a2ui({ catalog: "flux" })`` advertises flux components.
 */

import { describe, expect, it } from "vitest";

import { UI, T, activeCatalog } from "../../src/index.js";

describe("UI.withCatalog — catalog dispatch", () => {
  it("default catalog is basic", () => {
    expect(activeCatalog()).toBe("basic");
    const comp = UI.button("Go", { action: "go" });
    expect(comp.kind).toBe("Button");
  });

  it("withCatalog('flux', fn) swaps factory dispatch to flux", () => {
    const comp = UI.withCatalog("flux", () => UI.button("Go", { tone: "primary", action: "go" }));
    expect(comp.kind).toBe("FluxButton");
    expect(comp.props.tone).toBe("primary");
    expect(comp.props.label).toBe("Go");
    expect(comp.props.action).toEqual({ event: "go" });
  });

  it("restores catalog on exit (including after thrown errors)", () => {
    expect(() =>
      UI.withCatalog("flux", () => {
        expect(activeCatalog()).toBe("flux");
        throw new Error("boom");
      }),
    ).toThrow("boom");
    expect(activeCatalog()).toBe("basic");
    expect(UI.button("Hi", { action: "hi" }).kind).toBe("Button");
  });

  it("unknown catalog throws A2UIError with known list", () => {
    expect(() => UI.withCatalog("nope", () => UI.button("x"))).toThrow(/Unknown catalog "nope"/);
    expect(() => UI.withCatalog("nope", () => UI.button("x"))).toThrow(/flux/);
    expect(() => UI.withCatalog("nope", () => UI.button("x"))).toThrow(/basic/);
  });

  it("catalog scopes nest cleanly", () => {
    const outer = { kind: "" };
    const inner = { kind: "" };
    UI.withCatalog("flux", () => {
      outer.kind = UI.button("outer", { action: "a" }).kind;
      UI.withCatalog("basic", () => {
        inner.kind = UI.button("inner", { action: "b" }).kind;
      });
      // popping inner restores flux
      expect(activeCatalog()).toBe("flux");
    });
    expect(outer.kind).toBe("FluxButton");
    expect(inner.kind).toBe("Button");
    expect(activeCatalog()).toBe("basic");
  });

  it("every overloaded factory emits its flux equivalent inside a flux scope", () => {
    UI.withCatalog("flux", () => {
      expect(UI.button("go", { action: "go" }).kind).toBe("FluxButton");
      expect(UI.textField("Email").kind).toBe("FluxTextField");
      expect(UI.badge("new").kind).toBe("FluxBadge");
      expect(UI.progress({ value: 50 }).kind).toBe("FluxProgress");
      expect(UI.skeleton().kind).toBe("FluxSkeleton");
      expect(UI.markdown("# hi").kind).toBe("FluxMarkdown");
      expect(UI.link("docs", { href: "https://x" }).kind).toBe("FluxLink");
      expect(UI.banner({ title: "heads up", message: "note" }).kind).toBe("FluxBanner");
      expect(UI.stack().kind).toBe("FluxStack");
      // card accepts a FluxCardArgs object inside the flux scope.
      expect(UI.card({ id: "c1", emphasis: "subtle", padding: "md", body: "body text" }).kind).toBe(
        "FluxCard",
      );
    });
  });
});

describe("UI.theme", () => {
  it("attaches theme id to the enclosing surface", () => {
    const surface = UI.surface("flux_demo", [UI.theme("flux-dark"), UI.column([UI.text("hi")])]);
    expect(surface.theme).toEqual({ name: "flux-dark" });
  });

  it("theme marker can precede or follow the root component", () => {
    const a = UI.surface("a", [UI.theme("flux-light"), UI.text("x")]);
    const b = UI.surface("b", [UI.text("x"), UI.theme("flux-light")]);
    expect(a.theme).toEqual({ name: "flux-light" });
    expect(b.theme).toEqual({ name: "flux-light" });
  });

  it("surface without theme has empty theme object", () => {
    const s = UI.surface("no-theme", UI.text("hi"));
    expect(s.theme).toEqual({});
  });
});

describe("T.a2ui({ catalog })", () => {
  it("default (basic) still requires the a2ui-agent package", () => {
    expect(() => T.a2ui()).toThrow(/a2ui-agent/);
  });

  it("flux catalog returns an in-tree toolset with flux components", () => {
    const composite = T.a2ui({ catalog: "flux" });
    expect(composite.items.length).toBe(1);
    const spec = composite.items[0] as {
      type: string;
      catalog: string;
      components: string[];
      description: string;
      llmMetadata: Record<string, unknown>;
    };
    expect(spec.type).toBe("a2ui_flux");
    expect(spec.catalog).toBe("flux");
    expect(spec.components.length).toBeGreaterThanOrEqual(3);
    expect(spec.components).toContain("FluxButton");
    expect(spec.description).toContain("FluxButton");
    expect(spec.llmMetadata).toHaveProperty("FluxButton");
  });

  it("unknown catalog throws A2UIError", () => {
    expect(() => T.a2ui({ catalog: "nope" })).toThrow(/Unknown catalog "nope"/);
  });
});

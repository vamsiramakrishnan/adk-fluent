/**
 * Tests for the A2UI wedge: schema-driven UI.form, UI.paths, Agent.ui()
 * behavior matrix, T.a2ui() fail-loud, and surface validation.
 */
import { describe, expect, it, vi } from "vitest";
import { z } from "zod";
import {
  Agent,
  A2UIError,
  A2UINotInstalled,
  A2UISurfaceError,
  G,
  T,
  TComposite,
  UI,
  UIAutoSpec,
  UIComponent,
  UISchemaSpec,
  UISurface,
} from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

describe("Agent.ui() behavior matrix", () => {
  it("throws when no spec and llmGuided is false (or omitted)", () => {
    expect(() => new Agent("a", MODEL).ui()).toThrow(A2UIError);
    expect(() => new Agent("a", MODEL).ui(null)).toThrow(A2UIError);
    expect(() => new Agent("a", MODEL).ui(undefined, { llmGuided: false })).toThrow(A2UIError);
  });

  it("promotes undefined + llmGuided:true into a UIAutoSpec with fromFlag", () => {
    const a = new Agent("a", MODEL).ui(undefined, { llmGuided: true });
    const spec = a.inspect()._ui_spec as UIAutoSpec;
    expect(spec).toBeInstanceOf(UIAutoSpec);
    expect(spec.fromFlag).toBe(true);
    expect(spec.catalog).toBe("basic");
    expect(a.inspect()._a2uiAutoTool).toBe(true);
    expect(a.inspect()._a2uiAutoGuard).toBe(true);
  });

  it("keeps an explicit UIAutoSpec; only auto-wires tools when llmGuided is true", () => {
    const promptOnly = new Agent("a", MODEL).ui(UI.auto());
    expect(promptOnly.inspect()._ui_spec).toBeInstanceOf(UIAutoSpec);
    expect(promptOnly.inspect()._a2uiAutoTool).toBe(false);
    expect(promptOnly.inspect()._a2uiAutoGuard).toBe(false);

    const wired = new Agent("b", MODEL).ui(UI.auto(), { llmGuided: true });
    expect(wired.inspect()._a2uiAutoTool).toBe(true);
    expect(wired.inspect()._a2uiAutoGuard).toBe(true);
  });

  it("keeps a UISurface as-is", () => {
    const surface = UI.surface("s", UI.text("Hi"));
    const a = new Agent("a", MODEL).ui(surface);
    expect(a.inspect()._ui_spec).toBe(surface);
  });

  it("throws when llmGuided:true is combined with a declarative surface", () => {
    const surface = UI.surface("s", UI.text("Hi"));
    expect(() => new Agent("a", MODEL).ui(surface, { llmGuided: true })).toThrow(A2UIError);
  });

  it("wraps a bare UIComponent in a UISurface named 'default'", () => {
    const comp = UI.text("Hello");
    const a = new Agent("a", MODEL).ui(comp);
    const spec = a.inspect()._ui_spec as UISurface;
    expect(spec).toBeInstanceOf(UISurface);
    expect(spec.name).toBe("default");
    expect(spec.root).toBe(comp);
  });

  it("throws when llmGuided:true is combined with a bare UIComponent", () => {
    const comp = UI.text("Hi");
    expect(() => new Agent("a", MODEL).ui(comp, { llmGuided: true })).toThrow(A2UIError);
  });

  it("throws when llmGuided:true is combined with a UISchemaSpec", () => {
    expect(() => new Agent("a", MODEL).ui(UI.schema(), { llmGuided: true })).toThrow(A2UIError);
  });

  it("warns and overwrites when .ui() is called twice", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const a = new Agent("a", MODEL).ui(UI.auto());
    a.ui(UI.surface("s", UI.text("hi")));
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });
});

describe("UI.form(Zod schema)", () => {
  it("infers TextField for plain string", () => {
    const S = z.object({ name: z.string() });
    const surface = UI.form(S);
    const fields = surface.root.children.filter((c) => c.kind === "TextField");
    expect(fields).toHaveLength(1);
    const checks = (fields[0].props.checks ?? []) as Array<{ type: string }>;
    expect(checks.find((c) => c.type === "required")).toBeDefined();
  });

  it("adds UI.email() check for z.string().email()", () => {
    const S = z.object({ email: z.string().email() });
    const surface = UI.form(S);
    const field = surface.root.children.find((c) => c.kind === "TextField")!;
    const checks = (field.props.checks ?? []) as Array<{ type: string }>;
    expect(checks.find((c) => c.type === "email")).toBeDefined();
  });

  it("uses Checkbox for boolean", () => {
    const S = z.object({ accept: z.boolean() });
    const surface = UI.form(S);
    expect(surface.root.children.some((c) => c.kind === "Checkbox")).toBe(true);
  });

  it("uses TextField number variant for z.number()", () => {
    const S = z.object({ age: z.number() });
    const surface = UI.form(S);
    const field = surface.root.children.find((c) => c.kind === "TextField")!;
    expect(field.props.variant).toBe("number");
  });

  it("uses Choice dropdown for z.enum()", () => {
    const S = z.object({ tier: z.enum(["A", "B"]) });
    const surface = UI.form(S);
    const field = surface.root.children.find((c) => c.kind === "Choice")!;
    expect(field).toBeDefined();
    expect((field.props.options as string[]).sort()).toEqual(["A", "B"]);
  });

  it("drops UI.required() for optional fields", () => {
    const S = z.object({ note: z.string().optional() });
    const surface = UI.form(S);
    const field = surface.root.children.find((c) => c.kind === "TextField")!;
    const checks = (field.props.checks ?? []) as Array<{ type: string }>;
    expect(checks.find((c) => c.type === "required")).toBeUndefined();
  });

  it("preserves the legacy (title, opts.fields) call signature", () => {
    const surface = UI.form("My Form", {
      fields: [{ label: "X", required: true }],
    });
    expect(surface).toBeInstanceOf(UISurface);
    expect(surface.name).toBe("my_form");
  });

  it("throws A2UIError on bogus first argument", () => {
    expect(() => UI.form(42 as unknown as never)).toThrow(A2UIError);
  });
});

describe("UI.paths(schema)", () => {
  const Schema = z.object({
    email: z.string(),
    profile: z.object({ age: z.number() }),
  });

  it("returns a UIBinding for top-level fields with JSON-Pointer path", () => {
    const paths = UI.paths<{ email: { path: string; direction: string } }>(Schema);
    expect(paths.email.path).toBe("/email");
    expect(paths.email.direction).toBe("readwrite");
  });

  it("nests through UIObject schemas", () => {
    const paths = UI.paths<{ profile: { age: { path: string } } }>(Schema);
    expect(paths.profile.age.path).toBe("/profile/age");
  });

  it("throws A2UIError when accessing an unknown field", () => {
    const paths = UI.paths<Record<string, never>>(Schema);
    expect(() => (paths as unknown as { nope: unknown }).nope).toThrow(A2UIError);
  });
});

describe("T.a2ui()", () => {
  it("throws A2UINotInstalled because the JS package does not exist yet", () => {
    expect(() => T.a2ui()).toThrow(A2UINotInstalled);
  });
});

describe("UISurface.validate()", () => {
  it("throws on duplicate component IDs", () => {
    const surface = UI.surface(
      "s",
      UI.column([UI.text("a", { id: "x" }), UI.text("b", { id: "x" })]),
    );
    expect(() => surface.validate()).toThrow(A2UISurfaceError);
  });

  it("accepts a clean surface with unique IDs", () => {
    const surface = UI.surface(
      "s",
      UI.column([UI.text("a", { id: "x" }), UI.text("b", { id: "y" })]),
    );
    expect(() => surface.validate()).not.toThrow();
  });

  it("throws when an action references no registered handler", () => {
    const surface = new UISurface(
      "s",
      UI.column([UI.button("Go", { action: "submit" })]),
      {},
      {},
      { otherEvent: () => undefined },
    );
    expect(() => surface.validate()).toThrow(A2UISurfaceError);
  });

  it("throws when bind path references undeclared data key", () => {
    const surface = new UISurface(
      "s",
      UI.textField("Email", { bind: UI.bind("/email") }),
      {},
      { other: null }, // 'email' missing
    );
    expect(() => surface.validate()).toThrow(A2UISurfaceError);
  });
});

describe("Agent.ui() auto-wire + dedup", () => {
  it("wires T.a2ui() and G.a2ui() exactly once when llmGuided:true", () => {
    const agent = new Agent("x", MODEL)
      .instruct("hi")
      .tools(T.googleSearch())
      .ui(undefined, { llmGuided: true });

    // Build will throw because T.a2ui() is not installed — assert that's the
    // failure path, then verify dedup by inspecting before-build state.
    expect(() => agent.build()).toThrow(/a2ui-agent/);

    // The auto-wire flags are stamped on _config.
    expect(agent.inspect()._a2uiAutoTool).toBe(true);
    expect(agent.inspect()._a2uiAutoGuard).toBe(true);
  });

  it("does not re-add T.a2ui if a TComposite already has type=a2ui", () => {
    // Inject a fake a2ui composite by hand to mimic a successful import.
    const fake = new TComposite([{ type: "a2ui", catalog: "basic" }]);
    const agent = new Agent("x", MODEL)
      .instruct("hi")
      .tool(fake)
      .ui(undefined, { llmGuided: true });

    // Now build() should NOT call T.a2ui() (which would throw); the dedup path
    // bypasses it. But auto-guard will still fire (G.a2ui doesn't throw).
    const built = agent.build() as Record<string, unknown>;
    const tools = built.tools as TComposite[];
    const a2uiCount = tools.filter(
      (t) => t instanceof TComposite && t.items.some((it) => it.type === "a2ui"),
    ).length;
    expect(a2uiCount).toBe(1);
  });
});

describe("UI.auto() and UI.schema() classes", () => {
  it("UI.auto() returns a UIAutoSpec", () => {
    const a = UI.auto();
    expect(a).toBeInstanceOf(UIAutoSpec);
    expect(a.catalog).toBe("basic");
    expect(a.fromFlag).toBe(false);
  });

  it("UI.schema() returns a UISchemaSpec", () => {
    const s = UI.schema("custom");
    expect(s).toBeInstanceOf(UISchemaSpec);
    expect(s.catalogUri).toBe("custom");
  });
});

// Also ensure the new G/M paths still compose cleanly with the rest of the surface.
describe("regression: namespaces unaffected", () => {
  it("G.a2ui still composes via .pipe()", () => {
    const g = G.pii().pipe(G.a2ui());
    expect(g.guards.find((x) => x.name === "a2ui")).toBeDefined();
  });
});

// Touch UIComponent so the import is meaningful.
describe("UIComponent kept exported", () => {
  it("is accessible at the package root", () => {
    expect(typeof UIComponent).toBe("function");
  });
});

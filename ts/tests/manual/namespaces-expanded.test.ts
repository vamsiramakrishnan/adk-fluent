/**
 * Tests for expanded namespace modules: G, M, A, E, UI, T.
 */
import { describe, expect, it } from "vitest";
import { G, GuardViolation } from "../../src/namespaces/guards.js";
import { M } from "../../src/namespaces/middleware.js";
import { A } from "../../src/namespaces/artifacts.js";
import { E } from "../../src/namespaces/eval.js";
import { UI, UISurface } from "../../src/namespaces/ui.js";
import { T } from "../../src/namespaces/tools.js";

describe("G (Guards) — expanded", () => {
  it("G.regex() blocks matching patterns", () => {
    const guard = G.regex("secret", { action: "block" });
    expect(() => guard.guards[0].check("safe text")).not.toThrow();
    expect(() => guard.guards[0].check("contains secret data")).toThrow(GuardViolation);
  });

  it("G.regex() redacts when action=redact", () => {
    const guard = G.regex("\\d+", { action: "redact", replacement: "###" });
    const result = guard.guards[0].check("call 12345 now");
    expect(result).toBe("call ### now");
  });

  it("G.budget() carries token config", () => {
    const guard = G.budget({ maxTokens: 1000 });
    expect(guard.guards[0].name).toBe("budget");
    expect(guard.guards[0].config?.maxTokens).toBe(1000);
  });

  it("G.maxTurns() carries turn config", () => {
    const guard = G.maxTurns(5);
    expect(guard.guards[0].config?.maxTurns).toBe(5);
  });

  it("G.pii() defaults to block action", () => {
    const guard = G.pii();
    expect(guard.guards[0].config?.action).toBe("block");
  });

  it("G.toxicity() carries threshold", () => {
    const guard = G.toxicity({ threshold: 0.7 });
    expect(guard.guards[0].config?.threshold).toBe(0.7);
  });

  it("G.regexDetector() detects patterns", () => {
    const detector = G.regexDetector(["\\d{3}-\\d{4}"]);
    const findings = detector.detect("call me at 555-1234 today");
    expect(findings).toEqual(["555-1234"]);
  });

  it("G.when() wraps a guard with condition", () => {
    const guard = G.when((s) => s.flag === true, G.json());
    expect(guard.guards[0].name).toContain("when");
    expect(guard.guards[0].config?.condition).toBeDefined();
  });

  it("guards chain with .pipe()", () => {
    const chain = G.json()
      .pipe(G.length({ max: 100 }))
      .pipe(G.regex("\\bbad\\b"));
    expect(chain.guards.length).toBe(3);
  });
});

describe("M (Middleware)", () => {
  it("M.retry() defaults to 3 attempts", () => {
    const mw = M.retry();
    expect(mw.middlewares[0].name).toBe("retry");
    expect(mw.middlewares[0].config.maxAttempts).toBe(3);
  });

  it("M.cost() and M.latency() are simple no-config middlewares", () => {
    expect(M.cost().middlewares[0].name).toBe("cost");
    expect(M.latency().middlewares[0].name).toBe("latency");
  });

  it("M.timeout() carries seconds", () => {
    const mw = M.timeout(60);
    expect(mw.middlewares[0].config.seconds).toBe(60);
  });

  it("M.cache() defaults TTL to 300", () => {
    const mw = M.cache();
    expect(mw.middlewares[0].config.ttl).toBe(300);
  });

  it("M.scope() restricts to named agents", () => {
    const mw = M.scope(["agent1", "agent2"], M.log());
    expect(mw.middlewares[0].name).toBe("scope");
    expect(mw.middlewares[0].config.agents).toEqual(["agent1", "agent2"]);
  });

  it("M.circuitBreaker() has threshold and resetAfter", () => {
    const mw = M.circuitBreaker({ threshold: 10, resetAfter: 120 });
    expect(mw.middlewares[0].config.threshold).toBe(10);
    expect(mw.middlewares[0].config.resetAfter).toBe(120);
  });

  it("M.dedup() defaults window to 60", () => {
    expect(M.dedup().middlewares[0].config.window).toBe(60);
  });

  it("M.sample() carries rate", () => {
    const mw = M.sample(0.1, M.trace());
    expect(mw.middlewares[0].config.rate).toBe(0.1);
  });

  it("M.a2aRetry() carries A2A-specific config", () => {
    const mw = M.a2aRetry({ maxAttempts: 5, agents: ["remote1"] });
    expect(mw.middlewares[0].name).toBe("a2a_retry");
    expect(mw.middlewares[0].config.maxAttempts).toBe(5);
    expect(mw.middlewares[0].config.agents).toEqual(["remote1"]);
  });

  it("M.beforeModel() / M.afterModel() create hook middlewares", () => {
    const fn = () => undefined;
    expect(M.beforeModel(fn).middlewares[0].name).toBe("before_model");
    expect(M.afterModel(fn).middlewares[0].name).toBe("after_model");
  });

  it("middlewares chain with .pipe()", () => {
    const stack = M.retry().pipe(M.log()).pipe(M.cost()).pipe(M.latency());
    expect(stack.middlewares.length).toBe(4);
    expect(stack.middlewares.map((m) => m.name)).toEqual(["retry", "log", "cost", "latency"]);
  });
});

describe("A (Artifacts)", () => {
  it("A.publish() creates a publish op with default fromKey", () => {
    const a = A.publish("report.md");
    expect(a.ops[0].type).toBe("publish");
    expect(a.ops[0].config.filename).toBe("report.md");
    expect(a.ops[0].config.fromKey).toBe("report");
  });

  it("A.publish() respects custom fromKey", () => {
    const a = A.publish("data.json", { fromKey: "result" });
    expect(a.ops[0].config.fromKey).toBe("result");
  });

  it("A.snapshot() defaults intoKey from filename", () => {
    const a = A.snapshot("data.json");
    expect(a.ops[0].config.intoKey).toBe("data");
  });

  it("A.save() carries content", () => {
    const a = A.save("notes.txt", { content: "hello" });
    expect(a.ops[0].config.content).toBe("hello");
  });

  it("A.publishMany() creates multiple publish ops", () => {
    const a = A.publishMany([
      ["a.json", "valA"],
      ["b.json", "valB"],
    ]);
    expect(a.ops.length).toBe(2);
    expect(a.ops[0].config.filename).toBe("a.json");
    expect(a.ops[1].config.fromKey).toBe("valB");
  });

  it("A.asJson() parses JSON string in state", () => {
    const transform = A.asJson("payload");
    const result = transform.apply({ payload: '{"x": 1}' });
    expect(result.payload).toEqual({ x: 1 });
  });

  it("A.fromJson() serializes object to JSON string", () => {
    const transform = A.fromJson("payload");
    const result = transform.apply({ payload: { x: 1 } });
    expect(result.payload).toBe('{\n  "x": 1\n}');
  });

  it("A.asCsv() parses CSV with headers", () => {
    const transform = A.asCsv("data");
    const result = transform.apply({ data: "name,age\nAlice,30\nBob,25" });
    expect(result.data).toEqual([
      { name: "Alice", age: "30" },
      { name: "Bob", age: "25" },
    ]);
  });

  it("A.fromCsv() serializes objects to CSV", () => {
    const transform = A.fromCsv("data");
    const result = transform.apply({
      data: [
        { name: "Alice", age: 30 },
        { name: "Bob", age: 25 },
      ],
    });
    expect(result.data).toBe("name,age\nAlice,30\nBob,25");
  });

  it("A.fromMarkdown() converts headings", () => {
    const transform = A.fromMarkdown("doc");
    const result = transform.apply({ doc: "# Title\n## Subtitle" });
    expect(result.doc).toContain("<h1>Title</h1>");
    expect(result.doc).toContain("<h2>Subtitle</h2>");
  });

  it("A.mime exposes MIME constants", () => {
    expect(A.mime.json).toBe("application/json");
    expect(A.mime.markdown).toBe("text/markdown");
    expect(A.mime.png).toBe("image/png");
  });

  it("A.tool.save() creates a save tool spec", () => {
    const tool = A.tool.save();
    expect(tool.ops[0].type).toBe("tool_save");
    expect(tool.ops[0].config.name).toBe("save_artifact");
  });

  it("A.forLlm() returns a CTransform", () => {
    const ctx = A.forLlm("doc.md");
    expect(ctx.kind).toBe("artifact_for_llm");
    expect(ctx.config.filename).toBe("doc.md");
  });

  it("A operations chain with .pipe()", () => {
    const chain = A.publish("a.json", { fromKey: "x" }).pipe(
      A.snapshot("b.json", { intoKey: "y" }),
    );
    expect(chain.ops.length).toBe(2);
  });
});

describe("E (Evaluation)", () => {
  it("E.case_() creates an evaluation case", () => {
    const c = E.case_("What is 2+2?", { expect: "4" });
    expect(c.prompt).toBe("What is 2+2?");
    expect(c.expect).toBe("4");
  });

  it("E.responseMatch() defaults threshold to 0.8", () => {
    const crit = E.responseMatch();
    expect(crit.criteria[0].config.threshold).toBe(0.8);
  });

  it("E.trajectory() defaults match to exact", () => {
    const crit = E.trajectory();
    expect(crit.criteria[0].config.match).toBe("exact");
  });

  it("E.semanticMatch() carries judgeModel", () => {
    const crit = E.semanticMatch({ judgeModel: "gemini-2.5-pro" });
    expect(crit.criteria[0].config.judgeModel).toBe("gemini-2.5-pro");
  });

  it("E.rubric() carries rubric texts", () => {
    const crit = E.rubric(["Be polite", "Be accurate"]);
    expect(crit.criteria[0].config.texts).toEqual(["Be polite", "Be accurate"]);
  });

  it("E.custom() wraps user metric", () => {
    const fn = () => 0.9;
    const crit = E.custom("my_metric", fn);
    expect(crit.criteria[0].name).toBe("my_metric");
    expect(crit.criteria[0].config.fn).toBe(fn);
  });

  it("criteria chain with .pipe()", () => {
    const chain = E.responseMatch().pipe(E.trajectory()).pipe(E.safety());
    expect(chain.criteria.length).toBe(3);
  });

  it("E.suite() creates an EvalSuite", () => {
    const suite = E.suite({ name: "test-agent" });
    expect(suite).toBeDefined();
    suite.add(E.case_("hello"));
  });

  it("E.compare() creates a ComparisonSuite", () => {
    const cmp = E.compare({ name: "a1" }, { name: "a2" });
    expect(cmp).toBeDefined();
  });

  it("E.persona.expert() returns an expert persona", () => {
    const p = E.persona.expert();
    expect(p.id).toBe("expert");
    expect(p.behaviors.length).toBeGreaterThan(0);
  });

  it("E.persona.novice() returns a novice persona", () => {
    expect(E.persona.novice().id).toBe("novice");
  });

  it("E.persona.custom() creates custom persona", () => {
    const p = E.persona.custom("tester", "QA tester", ["Tries edge cases"]);
    expect(p.id).toBe("tester");
    expect(p.description).toBe("QA tester");
  });

  it("E.scenario() creates a conversation scenario", () => {
    const sc = E.scenario("Hi", ["ask question", "follow up"], {
      persona: E.persona.novice(),
    });
    expect(sc.start).toBe("Hi");
    expect(sc.plan.length).toBe(2);
    expect(sc.persona?.id).toBe("novice");
  });

  it("E.gate() wraps criteria as a quality gate", () => {
    const gate = E.gate(E.responseMatch(), { threshold: 0.9 });
    expect(gate.criteria[0].name).toBe("gate");
    expect(gate.criteria[0].config.threshold).toBe(0.9);
  });
});

describe("UI (A2UI components)", () => {
  it("UI.text() creates a text component", () => {
    const t = UI.text("Hello");
    expect(t.kind).toBe("Text");
    expect(t.props.text).toBe("Hello");
    expect(t.props.variant).toBe("body");
  });

  it("UI.heading() is an h1 alias", () => {
    const h = UI.heading("Title");
    expect(h.props.variant).toBe("h1");
  });

  it("UI.button() wraps label and action", () => {
    const b = UI.button("Submit", { variant: "primary", action: "submit" });
    expect(b.kind).toBe("Button");
    expect(b.props.variant).toBe("primary");
    expect(b.props.action).toBe("submit");
  });

  it("UI.textField() carries label and binding", () => {
    const tf = UI.textField("Name", { bind: UI.bind("/name") });
    expect(tf.props.label).toBe("Name");
    expect((tf.props.bind as { path: string }).path).toBe("/name");
  });

  it("UI.row() composes children horizontally", () => {
    const row = UI.row([UI.text("a"), UI.text("b")]);
    expect(row.kind).toBe("Row");
    expect(row.children.length).toBe(2);
  });

  it("UI.column() composes children vertically", () => {
    const col = UI.column([UI.heading("Title"), UI.button("OK")]);
    expect(col.kind).toBe("Column");
    expect(col.children.length).toBe(2);
  });

  it("component .row() chains components", () => {
    const composed = UI.text("a").row(UI.text("b"), UI.text("c"));
    expect(composed.kind).toBe("Row");
    expect(composed.children.length).toBe(3);
  });

  it("UI.bind() creates a JSON Pointer binding", () => {
    const b = UI.bind("/email", { direction: "write" });
    expect(b.path).toBe("/email");
    expect(b.direction).toBe("write");
  });

  it("UI.required() returns a UICheck", () => {
    const c = UI.required("Must fill in");
    expect(c.type).toBe("required");
    expect(c.config.message).toBe("Must fill in");
  });

  it("UI.email() creates an email check", () => {
    expect(UI.email().type).toBe("email");
  });

  it("UI.length() creates a length check", () => {
    const c = UI.length({ min: 3, max: 20 });
    expect(c.config.min).toBe(3);
    expect(c.config.max).toBe(20);
  });

  it("UI.surface() wraps a root component", () => {
    const s = UI.surface("main", UI.text("hello"));
    expect(s).toBeInstanceOf(UISurface);
    expect(s.name).toBe("main");
    expect(s.root.kind).toBe("Text");
  });

  it("UI.form() generates a form surface", () => {
    const form = UI.form("Login", {
      fields: [
        { label: "Email", bind: "/email", required: true },
        { label: "Password", bind: "/password", type: "obscured" },
      ],
      submit: "Sign In",
    });
    expect(form).toBeInstanceOf(UISurface);
    expect(form.name).toBe("login");
    expect(form.root.kind).toBe("Column");
    // Heading + 2 fields + submit button
    expect(form.root.children.length).toBe(4);
  });

  it("UI.dashboard() generates a dashboard surface", () => {
    const dash = UI.dashboard("Stats", {
      cards: [
        { label: "Users", value: "1234" },
        { label: "Revenue", value: "$5k" },
      ],
    });
    expect(dash).toBeInstanceOf(UISurface);
    expect(dash.root.kind).toBe("Column");
  });

  it("UI.confirm() generates a confirmation dialog", () => {
    const dlg = UI.confirm("Are you sure?");
    expect(dlg.name).toBe("confirm");
    expect(dlg.root.kind).toBe("Column");
  });

  it("UI.table() creates a table component with columns", () => {
    const t = UI.table([{ label: "Name", key: "name" }], { dataBind: "/items" });
    expect(t.kind).toBe("Table");
    expect(t.props.dataBind).toBe("/items");
  });

  it("UI.tabs() creates a tabs component", () => {
    const t = UI.tabs([
      { label: "Tab 1", content: UI.text("Content 1") },
      { label: "Tab 2", content: UI.text("Content 2") },
    ]);
    expect(t.kind).toBe("Tabs");
  });

  it("UI.checkbox() defaults value to false", () => {
    const c = UI.checkbox("Accept");
    expect(c.props.value).toBe(false);
  });

  it("UI.choice() carries options", () => {
    const c = UI.choice(["a", "b", "c"], { variant: "radio" });
    expect(c.kind).toBe("Choice");
    expect(c.props.variant).toBe("radio");
  });

  it("UI.slider() defaults to 0..100", () => {
    const s = UI.slider();
    expect(s.props.min).toBe(0);
    expect(s.props.max).toBe(100);
  });

  it("UI.formatNumber() returns a format spec", () => {
    const f = UI.formatNumber({ decimals: 2 });
    expect(f.type).toBe("formatNumber");
    expect(f.decimals).toBe(2);
  });

  it("UI.formatCurrency() defaults to USD", () => {
    expect((UI.formatCurrency() as { currency: string }).currency).toBe("USD");
  });

  it("UI.openUrl() returns an action spec", () => {
    expect((UI.openUrl("https://example.com") as { url: string }).url).toBe("https://example.com");
  });

  it("UIComponent.add() returns a new component with extra children", () => {
    const card = UI.card(UI.text("first"));
    const expanded = card.add(UI.text("second"));
    expect(expanded.children.length).toBe(2);
    expect(card.children.length).toBe(1); // immutable
  });
});

describe("T (Tools) — expanded", () => {
  it("T.fn() creates a function tool spec", () => {
    const fn = () => "result";
    const t = T.fn(fn);
    expect(t.items[0].type).toBe("function");
    expect(t.items[0].fn).toBe(fn);
    expect(t.items[0].confirm).toBe(false);
  });

  it("T.fn() with confirm flag", () => {
    const t = T.fn(() => undefined, { confirm: true });
    expect(t.items[0].confirm).toBe(true);
  });

  it("T.googleSearch() creates a builtin search tool", () => {
    expect(T.googleSearch().items[0].type).toBe("google_search");
  });

  it("T.skill() wraps a single SKILL.md path into a skill_toolset", () => {
    const t = T.skill("/skills/researcher");
    expect(t.items[0].type).toBe("skill_toolset");
    expect((t.items[0].paths as string[]).length).toBe(1);
    expect((t.items[0].paths as string[])[0]).toBe("/skills/researcher");
  });

  it("T.skill() accepts a list of paths", () => {
    const t = T.skill(["/skills/a", "/skills/b"]);
    expect((t.items[0].paths as string[]).length).toBe(2);
  });

  it("T.mcp() with URL string", () => {
    const t = T.mcp("https://mcp.example.com");
    expect(t.items[0].type).toBe("mcp");
    expect((t.items[0].params as { url: string }).url).toBe("https://mcp.example.com");
  });

  it("T.openapi() carries spec", () => {
    const t = T.openapi("https://api.example.com/openapi.json");
    expect(t.items[0].type).toBe("openapi");
  });

  it("T.a2a() defaults timeout to 600", () => {
    const t = T.a2a("https://agent.example.com/.well-known/agent.json");
    expect(t.items[0].timeout).toBe(600);
  });

  it("T.confirm() wraps a tool with confirmation", () => {
    const t = T.confirm(
      T.fn(() => undefined),
      "Are you sure?",
    );
    expect(t.items[0].confirm).toBe(true);
    expect(t.items[0].confirmMessage).toBe("Are you sure?");
  });

  it("T.timeout() wraps a tool with seconds", () => {
    const t = T.timeout(
      T.fn(() => undefined),
      30,
    );
    expect(t.items[0].timeout).toBe(30);
  });

  it("T.cache() wraps a tool with TTL", () => {
    const t = T.cache(
      T.fn(() => undefined),
      { ttl: 600 },
    );
    expect(t.items[0].cache).toBe(true);
    expect(t.items[0].ttl).toBe(600);
  });

  it("T.mock() creates a mock tool", () => {
    const t = T.mock("test_tool", { returns: "mocked" });
    expect(t.items[0].type).toBe("mock");
    expect(t.items[0].name).toBe("test_tool");
    expect(t.items[0].returns).toBe("mocked");
  });

  it("tools chain with .pipe()", () => {
    const chain = T.googleSearch().pipe(T.fn(() => undefined));
    expect(chain.items.length).toBe(2);
  });
});

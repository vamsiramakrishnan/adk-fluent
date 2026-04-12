/**
 * 58 — A2UI basics: surfaces, components, and `agent.ui()`
 *
 * The `UI` namespace builds declarative component trees that an agent can
 * advertise via `.ui()`. Components are immutable `UIComponent` objects;
 * `UI.surface(name, root)` wraps a component tree as a named surface.
 *
 * Cookbook covers:
 *   - text / button / textField / image / row / column factories
 *   - data binding via UI.bind() + validation checks (UI.required, UI.email)
 *   - attaching a surface to an Agent via .ui() — stored in `_ui_spec`
 *   - LLM-guided mode via UI.auto()
 */
import assert from "node:assert/strict";
import { Agent, UI, UIComponent, UISurface } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

// Build a small login surface declaratively.
const heading = UI.heading("Sign in");
const emailField = UI.textField("Email", {
  bind: UI.bind("/credentials/email"),
  checks: [UI.required("Email is required"), UI.email()],
});
const passwordField = UI.textField("Password", {
  variant: "obscured",
  bind: UI.bind("/credentials/password"),
  checks: [UI.required(), UI.length({ min: 8, msg: "Min 8 chars" })],
});
const submit = UI.button("Sign in", { variant: "primary", action: "submit_login" });

const root = UI.column([heading, emailField, passwordField, submit]);
assert.ok(root instanceof UIComponent);
assert.equal(root.kind, "Column");
assert.equal(root.children.length, 4);
assert.equal(root.children[0].kind, "Text");
assert.equal(root.children[1].kind, "TextField");

// The submit button stores its action in props.
const submitProps = submit.props as { action: string; variant: string };
assert.equal(submitProps.action, "submit_login");
assert.equal(submitProps.variant, "primary");

// TextField checks are propagated to props.
const emailProps = emailField.props as { checks: Array<{ type: string }>; bind: { path: string } };
assert.equal(emailProps.checks.length, 2);
assert.equal(emailProps.checks[0].type, "required");
assert.equal(emailProps.checks[1].type, "email");
assert.equal(emailProps.bind.path, "/credentials/email");

// Wrap as a named surface.
const surface = UI.surface("login", root);
assert.ok(surface instanceof UISurface);
assert.equal(surface.name, "login");
assert.equal(surface.root, root);

// Attach the surface to an agent — stored as a private `_ui_spec` key.
const loginAgent = new Agent("login_helper", MODEL)
  .instruct("Help the user sign in.")
  .ui(surface);

assert.equal(loginAgent.inspect()._ui_spec, surface);
// Build strips private keys.
const built = loginAgent.build() as Record<string, unknown>;
assert.equal(built._ui_spec, undefined);
assert.equal(built.name, "login_helper");

// LLM-guided mode: agent picks the UI dynamically from a catalog.
const auto = UI.auto({ catalog: "basic" });
assert.equal((auto as { type: string }).type, "a2ui_auto");
const autoAgent = new Agent("ui_auto", MODEL).instruct("Render a UI.").ui(auto);
assert.equal(autoAgent.inspect()._ui_spec, auto);

// Row composition via the chained `.row()` method on a component.
const toolbar = UI.text("Hello").row(UI.button("OK"), UI.button("Cancel"));
assert.equal(toolbar.kind, "Row");
assert.equal(toolbar.children.length, 3);

export { surface, loginAgent };

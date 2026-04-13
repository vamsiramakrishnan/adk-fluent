/**
 * 68 — A2UI Basics: Declarative Agent-to-UI Composition
 *
 * Demonstrates the full UI namespace for building rich agent UIs declaratively.
 *
 * Cookbook covers:
 *   - Component factories: text, button, textField, image, row, column
 *   - Data binding via UI.bind() + validation (UI.required, UI.email, UI.length)
 *   - Named surfaces via UI.surface()
 *   - Presets: form, dashboard, wizard, confirm, table
 *   - Generic component escape hatch via UI.component()
 */
import assert from "node:assert/strict";
import { UI, UIComponent, UISurface } from "../../src/index.js";

// --- 1. Component creation ---
const text = UI.text("Hello, World!");
assert.equal(text.kind, "Text");

const button = UI.button("Click Me");
assert.equal(button.kind, "Button");

const field = UI.textField("Name");
assert.equal(field.kind, "TextField");

const img = UI.image("https://example.com/logo.png", { fit: "cover" });
assert.equal(img.kind, "Image");

// --- 2. Layout composition ---

// Row layout (horizontal)
const row = UI.row([UI.text("Left"), UI.text("Right")]);
assert.equal(row.kind, "Row");
assert.equal(row.children.length, 2);

// Column layout (vertical)
const col = UI.column([UI.text("Top"), UI.text("Bottom")]);
assert.equal(col.kind, "Column");
assert.equal(col.children.length, 2);

// Nested layout: row inside a column
const layout = UI.column([UI.row([UI.text("A"), UI.text("B")]), UI.text("Footer")]);
assert.equal(layout.kind, "Column");
assert.equal(layout.children.length, 2);
assert.equal(layout.children[0].kind, "Row");

// --- 3. Data binding ---
const binding = UI.bind("/user/name");
assert.equal(binding.path, "/user/name");
assert.equal(binding.direction, "readwrite");

// --- 4. Validation checks ---
const required = UI.required("Name is required");
assert.equal(required.type, "required");

const emailCheck = UI.email("Invalid email");
assert.equal(emailCheck.type, "email");

const lengthCheck = UI.length({ min: 3, max: 100 });
assert.equal(lengthCheck.type, "length");

// --- 5. Named surface ---
const surface = UI.surface(
  "contact_form",
  UI.column([UI.text("Contact Us"), UI.textField("Name")]),
);
assert.ok(surface instanceof UISurface);
assert.equal(surface.name, "contact_form");
assert.equal(surface.root.kind, "Column");

// --- 6. Presets ---

// Form preset
const form = UI.form("Feedback", {
  fields: [
    { label: "Name", bind: "/name", required: true },
    { label: "Email", bind: "/email", required: true },
    { label: "Message", bind: "/message", type: "longText" },
  ],
  submit: "Send",
});
assert.ok(form instanceof UISurface);
assert.equal(form.name, "feedback");
assert.equal(form.root.kind, "Column");

// Dashboard preset
const dashboard = UI.dashboard("Metrics", {
  cards: [
    { label: "Users", value: "1,234" },
    { label: "Revenue", value: "$50K" },
  ],
});
assert.ok(dashboard instanceof UISurface);
assert.equal(dashboard.name, "metrics");

// Confirm dialog preset
const confirm = UI.confirm("Delete this item?");
assert.ok(confirm instanceof UISurface);
assert.equal(confirm.name, "confirm");

// Table component
const table = UI.table(
  [
    { label: "Name", key: "name" },
    { label: "Email", key: "email" },
  ],
  { dataBind: "/users" },
);
assert.ok(table instanceof UIComponent);
assert.equal(table.kind, "Table");
const tableProps = table.props as { columns: Array<{ key: string }>; dataBind: string };
assert.equal(tableProps.columns.length, 2);
assert.equal(tableProps.dataBind, "/users");

// Wizard preset
const wizard = UI.wizard("Setup", {
  steps: [
    { label: "Welcome", content: UI.text("Hi") },
    { label: "Done", content: UI.text("Bye") },
  ],
});
assert.ok(wizard instanceof UISurface);
assert.equal(wizard.name, "setup");

// --- 7. Generic component (escape hatch) ---
const custom = UI.component("BarChart", { data: "test", x: "date", y: "value" });
assert.equal(custom.kind, "BarChart");

export { surface, form, dashboard, confirm, table, wizard, custom };

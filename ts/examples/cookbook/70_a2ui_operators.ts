/**
 * 70 — A2UI Operators: UI Composition with Row/Column
 *
 * Demonstrates declarative UI layout composition using the row/column
 * factories and the chained `.row()` method on UIComponent.
 *
 * Cookbook covers:
 *   - UI.row() and UI.column() layout factories
 *   - Chained .row() method for inline composition
 *   - Nested layouts for complex form structures
 *   - Surface wrapping for compilation
 */
import assert from "node:assert/strict";
import { UI, UIComponent, UISurface } from "../../src/index.js";

// --- 1. Row layout ---
const row = UI.row([UI.text("Left"), UI.text("Right")]);
assert.equal(row.kind, "Row");
assert.equal(row.children.length, 2);

// --- 2. Column layout ---
const col = UI.column([UI.text("Top"), UI.text("Bottom")]);
assert.equal(col.kind, "Column");
assert.equal(col.children.length, 2);

// --- 3. Nested layout: header row above a footer ---
const layout = UI.column([UI.row([UI.text("Logo"), UI.text("Nav")]), UI.text("Footer")]);
assert.equal(layout.kind, "Column");
assert.equal(layout.children.length, 2);
assert.equal(layout.children[0].kind, "Row");

// --- 4. Complex form layout ---
const formLayout = UI.column([
  UI.text("Sign Up", { variant: "h1" }),
  UI.row([UI.textField("First Name"), UI.textField("Last Name")]),
  UI.textField("Email"),
  UI.row([UI.button("Submit"), UI.button("Cancel")]),
]);
assert.equal(formLayout.kind, "Column");
assert.equal(formLayout.children.length, 4);
assert.equal(formLayout.children[0].kind, "Text"); // heading
assert.equal(formLayout.children[1].kind, "Row"); // name row
assert.equal(formLayout.children[2].kind, "TextField"); // email
assert.equal(formLayout.children[3].kind, "Row"); // buttons row

// --- 5. Surface wrapping ---
const surface = UI.surface("signup", formLayout);
assert.ok(surface instanceof UISurface);
assert.equal(surface.name, "signup");
assert.equal(surface.root, formLayout);

// --- 6. Chained .row() method ---
const toolbar = UI.text("Hello").row(UI.button("OK"), UI.button("Cancel"));
assert.equal(toolbar.kind, "Row");
assert.equal(toolbar.children.length, 3);
assert.equal(toolbar.children[0].kind, "Text");
assert.equal(toolbar.children[1].kind, "Button");
assert.equal(toolbar.children[2].kind, "Button");

// --- 7. Three-column grid ---
const gridRow = UI.row([UI.text("A"), UI.text("B"), UI.text("C")]);
assert.equal(gridRow.kind, "Row");
assert.equal(gridRow.children.length, 3);

// --- 8. Deeply nested: dashboard layout ---
const dashLayout = UI.column([
  UI.text("Dashboard", { variant: "h1" }),
  UI.row([
    UI.column([UI.text("Revenue", { variant: "caption" }), UI.text("$1.2M", { variant: "h3" })]),
    UI.column([UI.text("Orders", { variant: "caption" }), UI.text("8,431", { variant: "h3" })]),
  ]),
  UI.text("Last updated: just now", { variant: "caption" }),
]);
assert.equal(dashLayout.kind, "Column");
assert.equal(dashLayout.children.length, 3);
assert.equal(dashLayout.children[1].kind, "Row");
assert.equal(dashLayout.children[1].children[0].kind, "Column");

export { surface, formLayout, toolbar, dashLayout };

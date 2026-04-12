/**
 * 59 — A2UI presets: forms, dashboards, wizards, confirms, tables
 *
 * The `UI` namespace ships preset surface generators that compile common
 * patterns from a compact field/card spec.
 *
 *   UI.form        — heading + text fields + submit button
 *   UI.dashboard   — heading + row of metric cards
 *   UI.confirm     — message + Yes/No row
 *   UI.wizard      — multi-step container
 *   UI.table       — column-driven data table component
 */
import assert from "node:assert/strict";
import { UI, UISurface, UIComponent } from "../../src/index.js";

// 1. Form preset — auto-generates fields with required validation.
const signupForm = UI.form("Sign up", {
  fields: [
    { label: "Full name", bind: "/user/name", required: true },
    { label: "Email", bind: "/user/email", required: true },
    { label: "Bio", bind: "/user/bio", type: "longText" },
  ],
  submit: "Create account",
  submitAction: "create_account",
});

assert.ok(signupForm instanceof UISurface);
assert.equal(signupForm.name, "sign_up");
const formRoot = signupForm.root;
assert.equal(formRoot.kind, "Column");
// heading + 3 fields + submit
assert.equal(formRoot.children.length, 5);
assert.equal(formRoot.children[0].kind, "Text"); // heading
assert.equal(formRoot.children[1].kind, "TextField");
assert.equal(formRoot.children[4].kind, "Button");

// Required fields carry a `required` check.
const nameProps = formRoot.children[1].props as { checks?: Array<{ type: string }> };
assert.ok(nameProps.checks);
assert.equal(nameProps.checks[0].type, "required");

// Optional bio has no checks.
const bioProps = formRoot.children[3].props as { checks?: unknown };
assert.equal(bioProps.checks, undefined);

// 2. Dashboard preset — heading + row of metric cards.
const dashboard = UI.dashboard("Sales overview", {
  cards: [
    { label: "Revenue", value: "$1.2M" },
    { label: "Orders", value: "8,431" },
    { label: "Refunds", value: "12" },
  ],
});
assert.ok(dashboard instanceof UISurface);
const dashRoot = dashboard.root;
assert.equal(dashRoot.kind, "Column");
assert.equal(dashRoot.children[1].kind, "Row");
assert.equal(dashRoot.children[1].children.length, 3);
const firstCard = dashRoot.children[1].children[0];
assert.equal(firstCard.kind, "Card");

// 3. Confirm dialog preset.
const confirmation = UI.confirm("Delete this project?", {
  yes: "Delete",
  no: "Cancel",
  yesAction: "delete_project",
});
assert.equal(confirmation.name, "confirm");
const confirmRoot = confirmation.root;
assert.equal(confirmRoot.children[1].kind, "Row");
const yesBtn = confirmRoot.children[1].children[0];
const yesProps = yesBtn.props as { action: string };
assert.equal(yesProps.action, "delete_project");

// 4. Table component (returns a UIComponent, not a surface).
const ordersTable = UI.table(
  [
    { label: "ID", key: "id" },
    { label: "Customer", key: "customer" },
    { label: "Total", key: "total" },
  ],
  { dataBind: "/orders" },
);
assert.ok(ordersTable instanceof UIComponent);
assert.equal(ordersTable.kind, "Table");
const tableProps = ordersTable.props as {
  columns: Array<{ key: string }>;
  dataBind: string;
};
assert.equal(tableProps.columns.length, 3);
assert.equal(tableProps.dataBind, "/orders");

// 5. Wizard preset — heading + Wizard component holding the steps.
const wizard = UI.wizard("Onboarding", {
  steps: [
    { label: "Profile", content: UI.text("Tell us about yourself") },
    { label: "Plan", content: UI.text("Pick a plan") },
    { label: "Done", content: UI.text("All set!") },
  ],
});
assert.equal(wizard.name, "onboarding");
const wizRoot = wizard.root;
assert.equal(wizRoot.children[1].kind, "Wizard");
const wizProps = wizRoot.children[1].props as { steps: unknown[] };
assert.equal(wizProps.steps.length, 3);

export { signupForm, dashboard, confirmation, ordersTable, wizard };

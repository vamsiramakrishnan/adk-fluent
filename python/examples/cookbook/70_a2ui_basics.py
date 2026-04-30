"""A2UI Basics — Customer Onboarding UI for a SaaS Platform

Real-world scenario: building the UI surfaces for a customer onboarding
agent. The agent collects customer info via a form, shows account metrics
on a dashboard, confirms plan selection, and displays a user table.

Concepts:
  UI.text / .button / .text_field — component factories
  UI.bind()          — two-way data binding to JSON Pointer paths
  UI.required()      — validation checks
  | (Row), >> (Col)  — layout composition operators
  UI.surface()       — named compilation root
  compile_surface()  — Python tree → flat A2UI JSON messages
  Presets: UI.form(), UI.dashboard(), UI.confirm(), UI.table(), UI.wizard()
"""

from adk_fluent._ui import (
    UI,
    UIBinding,
    UICheck,
    UIComponent,
    UISurface,
    compile_surface,
)

# --- 1. Onboarding form — component creation + composition ---

header = UI.text("Welcome to Acme", variant="h2")
name_field = UI.text_field("Full Name", bind=UI.bind("/customer/name"), checks=[UI.required()])
email_field = UI.text_field("Email", bind=UI.bind("/customer/email"), checks=[UI.required(), UI.email()])
company_field = UI.text_field("Company", bind=UI.bind("/customer/company"))

assert header._kind == "Text"
assert name_field._kind == "TextField"
assert isinstance(UI.bind("/customer/name"), UIBinding)
assert isinstance(UI.required(), UICheck)

# Compose layout: header on top, fields stacked vertically
onboarding_layout = header >> name_field >> email_field >> company_field
assert onboarding_layout._kind == "Column"
assert len(onboarding_layout._children) >= 2  # binary >> nests; flatten is internal

# Side-by-side buttons
cancel_btn = UI.button(child=UI.text("Cancel"))
submit_btn = UI.button("primary", child=UI.text("Continue"))
actions = cancel_btn | submit_btn
assert actions._kind == "Row"

# Full form
form_layout = onboarding_layout >> actions
assert form_layout._kind == "Column"

# --- 2. Surface creation + theme + data ---
onboarding_surface = UI.surface("onboarding", form_layout)
assert isinstance(onboarding_surface, UISurface)
assert onboarding_surface.name == "onboarding"

themed = onboarding_surface.with_theme(primaryColor="#2563eb", agentDisplayName="Acme Onboarding")
assert len(themed.theme) == 2

with_defaults = onboarding_surface.with_data(customer={"name": "", "email": "", "company": ""})
assert len(with_defaults.data) == 1

# --- 3. Compilation to A2UI protocol ---
msgs = compile_surface(onboarding_surface)
assert len(msgs) == 2  # createSurface + updateComponents

create_msg = msgs[0]
assert create_msg["createSurface"]["surfaceId"] == "onboarding"

update_msg = msgs[1]
components = update_msg["updateComponents"]["components"]
assert len(components) >= 5  # Column + 4 fields + buttons

# --- 4. Preset: schema-driven feedback form ---
form = UI.form("Customer Feedback", fields={"name": "text", "email": "email", "message": "longText"})
assert isinstance(form, UISurface)

# --- 5. Preset: account metrics dashboard ---
dashboard = UI.dashboard("Account Overview", cards=[
    {"title": "Active Users", "bind": "/stats/active_users"},
    {"title": "MRR", "bind": "/stats/mrr"},
    {"title": "Churn Rate", "bind": "/stats/churn"},
])
assert isinstance(dashboard, UISurface)
dash_msgs = compile_surface(dashboard)
assert any("createSurface" in m for m in dash_msgs)

# --- 6. Preset: plan upgrade confirmation ---
confirm = UI.confirm("Upgrade to Enterprise plan? ($499/mo, billed annually)")
assert isinstance(confirm, UISurface)

# --- 7. Preset: team member table ---
table = UI.table(["Name", "Email", "Role"], data_bind="/team/members")
assert isinstance(table, UISurface)

# --- 8. Preset: onboarding wizard ---
wizard = UI.wizard("Account Setup", steps=[
    ("Company Info", UI.text_field("Company Name", bind=UI.bind("/company/name"))),
    ("Plan Selection", UI.text("Choose your plan") >> (UI.button("Starter") | UI.button("Pro") | UI.button("Enterprise"))),
    ("Confirmation", UI.text("Review your selections and confirm.")),
])
assert isinstance(wizard, UISurface)

# --- 9. Generic component (escape hatch for custom visualizations) ---
usage_chart = UI.component("BarChart", data="/stats/usage_history", x="month", y="api_calls")
assert usage_chart._kind == "BarChart"

print("All A2UI onboarding assertions passed!")

"""
Dynamic A2UI Agent: LLM-Driven UI Generation

Demonstrates the core A2UI value proposition: the LLM itself designs
and generates interactive UI surfaces based on user intent.

.ui(UI.auto()) does all the heavy lifting:
      1. Attaches SendA2uiToClientToolset (gives LLM a send_a2ui_json_to_client tool)
  2. Injects the full A2UI JSON Schema at LLM request time
  3. The LLM reads the schema, designs UIs, and sends valid A2UI JSON

Usage:
    cd examples
    adk web a2ui_dynamic
"""

from __future__ import annotations

from adk_fluent import Agent, P, UI
from dotenv import load_dotenv

load_dotenv()


# --- Domain tools (provide real data for the LLM to visualize) ---


def get_expense_categories() -> str:
    """Get the list of valid expense categories and their policies."""
    return (
        "Categories: Travel (max $5000/trip), Meals ($75/person limit), "
        "Software (pre-approval >$500), Equipment (pre-approval >$1000), "
        "Training ($2000/year budget), Office Supplies (no limit)"
    )


def get_sales_metrics(period: str) -> str:
    """Get sales metrics for a given time period.

    Args:
        period: Time period like 'this month', 'last quarter', 'YTD'.
    """
    return (
        f"Sales metrics for {period}: "
        "Revenue: $1,247,000 (+12% MoM), "
        "Orders: 8,421 (+8% MoM), "
        "Avg Order Value: $148.09 (-3% MoM), "
        "Conversion Rate: 3.2% (+0.4pp MoM), "
        "New Customers: 1,205 (+15% MoM), "
        "Churn Rate: 2.1% (-0.3pp MoM)"
    )


def get_deployment_status(service: str) -> str:
    """Get the current deployment status and readiness for a service.

    Args:
        service: Service name to check deployment status for.
    """
    return (
        f"Deployment status for {service}: "
        "Current version: v2.0.3 (stable), "
        "Pending version: v2.1.0, "
        "Tests: 847/847 passing, "
        "Staging: deployed and verified, "
        "Rollback plan: automatic via canary, "
        "Affected services: auth-service, api-gateway, user-service, "
        "Estimated downtime: 0 (rolling deploy), "
        "Last deploy: 3 days ago (no incidents)"
    )


def get_launch_checklist(feature: str) -> str:
    """Get the pre-launch checklist items for a feature.

    Args:
        feature: Feature name to get checklist for.
    """
    return (
        f"Pre-launch checklist for {feature}: "
        "1. Unit tests passing (DONE), "
        "2. Integration tests passing (DONE), "
        "3. Load test completed (DONE - handles 2x expected traffic), "
        "4. Security review (DONE - no critical findings), "
        "5. Documentation updated (PENDING), "
        "6. Changelog entry added (PENDING), "
        "7. Feature flag configured (DONE), "
        "8. Monitoring dashboards set up (DONE), "
        "9. Rollback procedure documented (DONE), "
        "10. Stakeholder sign-off (PENDING)"
    )


# --- Agent: .ui(UI.auto()) = full A2UI in one line ---

root_agent = (
    Agent("dynamic_ui", "gemini-2.5-flash")
    .instruct(
        P.role(
            "You are a smart assistant that creates interactive UIs. "
            "Analyze user intent and respond with BOTH text AND a rich A2UI surface."
        )
        + P.constraint(
            "Use domain tools to get real data first",
            "Then use send_a2ui_json_to_client to send a beautiful UI",
            "Forms for data collection (TextField, ChoicePicker, CheckBox)",
            "Dashboards for metrics (Cards, Text, Row/Column layout)",
            "Confirmation dialogs for approvals (details + action Buttons)",
            "Checklists for readiness checks (CheckBox components)",
            "Design beautiful, practical UIs with proper hierarchy",
        )
    )
    .tool(get_expense_categories)
    .tool(get_sales_metrics)
    .tool(get_deployment_status)
    .tool(get_launch_checklist)
    .ui(UI.auto())
    .build()
)

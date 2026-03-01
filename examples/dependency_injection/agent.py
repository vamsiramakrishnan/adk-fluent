"""
Dependency Injection: Multi-Environment Deployment (Dev/Staging/Prod)

Converted from cookbook example: 47_dependency_injection.py

Usage:
    cd examples
    adk web dependency_injection
"""

import inspect

from adk_fluent import Agent
from adk_fluent.di import inject_resources
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)


def query_patient_records(patient_id: str, db_connection: object) -> str:
    """Query patient records from the database."""
    return f"Records for patient {patient_id} from {db_connection}"


# Scenario: A healthcare agent deployed across dev, staging, and production.
# Each environment connects to a different database. The LLM should never
# see or influence which database is used -- that's an infrastructure concern.

# Production deployment: inject the production database connection
prod_agent = (
    Agent("patient_query")
    .model("gemini-2.5-flash")
    .instruct("Query patient records by ID.")
    .tool(query_patient_records)
    .inject(db_connection="prod_ehr_db")
)

# Staging deployment: same agent definition, different database
staging_agent = (
    Agent("patient_query")
    .model("gemini-2.5-flash")
    .instruct("Query patient records by ID.")
    .tool(query_patient_records)
    .inject(db_connection="staging_ehr_db")
)

# Dev deployment: uses an in-memory mock database
dev_agent = (
    Agent("patient_query")
    .model("gemini-2.5-flash")
    .instruct("Query patient records by ID.")
    .tool(query_patient_records)
    .inject(db_connection="dev_mock_db")
)

root_agent = dev_agent.build()

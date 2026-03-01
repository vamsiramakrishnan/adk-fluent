"""
Contracts and Testing: Medical Imaging Pipeline with Strict Data Contracts

Converted from cookbook example: 46_contracts_and_testing.py

Usage:
    cd examples
    adk web contracts_and_testing
"""

from pydantic import BaseModel

from adk_fluent import Agent
from adk_fluent.testing import check_contracts, mock_backend
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)


class ImagingStudy(BaseModel):
    """Structured data contract for a medical imaging study."""

    modality: str  # CT, MRI, X-ray, etc.
    body_region: str  # chest, abdomen, brain, etc.
    finding_count: int  # number of notable findings


# 1. Declare data contracts between pipeline stages
# The DICOM parser produces an ImagingStudy; the diagnosis agent consumes it
imaging_pipeline = Agent("dicom_parser").produces(ImagingStudy) >> Agent("diagnosis_agent").consumes(ImagingStudy)

# 2. Verify at build time (no LLM calls needed)
# Catches mismatches before the pipeline ever runs on real patient data
issues = check_contracts(imaging_pipeline.to_ir())

# 3. Create a mock backend for deterministic testing
# Simulates the full pipeline without any LLM or PACS system calls
mb = mock_backend(
    {
        "dicom_parser": {"modality": "CT", "body_region": "chest", "finding_count": 3},
        "diagnosis_agent": "Findings: 2 nodules, 1 consolidation. Recommend follow-up CT in 3 months.",
    }
)

# Build the pipeline for deployment
agent_fluent = imaging_pipeline.build()

root_agent = agent_fluent

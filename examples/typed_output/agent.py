"""
Structured Invoice Parsing: Typed Output Contracts with @ Operator

Converted from cookbook example: 31_typed_output.py

Usage:
    cd examples
    adk web typed_output
"""


# --- Tools & Callbacks ---

from pydantic import BaseModel


class Invoice(BaseModel):
    vendor: str
    total_amount: float
    due_date: str


from adk_fluent import Agent, Pipeline
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# @ binds a Pydantic model as the output schema — the LLM must return
# data matching this structure, enabling downstream type-safe processing
parser_fluent = (
    Agent("invoice_parser")
    .model("gemini-2.5-flash")
    .instruct("Parse the uploaded invoice image and extract structured data.")
    @ Invoice
)

# @ is immutable — original unchanged, so you can build variants
base_extractor = Agent("extractor").model("gemini-2.5-flash").instruct("Extract financial data.")
typed_extractor = base_extractor @ Invoice
# base_extractor has no schema, typed_extractor does


class PurchaseOrder(BaseModel):
    order_id: str
    line_items: list[str]
    subtotal: float


# Composes with >> — typed parser feeds structured data into downstream agents
accounts_pipeline = (
    Agent("ocr_agent").model("gemini-2.5-flash").instruct("Perform OCR on the uploaded document and extract raw text.")
    >> Agent("invoice_parser").model("gemini-2.5-flash").instruct("Parse the raw text into structured invoice fields.")
    @ Invoice
    >> Agent("bookkeeper").model("gemini-2.5-flash").instruct("Record the parsed invoice in the general ledger.")
)

# @ preserves all existing config — output_key and schema coexist
detailed_parser = (
    Agent("detailed_parser")
    .model("gemini-2.5-flash")
    .instruct("Extract every line item from the purchase order with amounts.")
    .writes("parsed_po")
    @ PurchaseOrder
)

root_agent = detailed_parser.build()

# Structured Data

Agents that return free-form text are fine for chat, but production pipelines need predictable data. A classifier must emit a category string that a router can branch on. An extraction step must produce a JSON object that a downstream formatter can render. adk-fluent provides three complementary mechanisms for structured data flow: storing output in session state, enforcing typed output schemas, and declaring input schemas for tool-invoked agents.

## Storing Output in State: `.outputs(key)`

`.outputs(key)` is an alias for ADK's `output_key`. When an agent finishes, its response text is written to session state under the given key. Other agents can then read that value through template variable substitution in their instructions.

### Basic usage

```python
from adk_fluent import Agent

classifier = (
    Agent("classifier", "gemini-2.5-flash")
    .instruct("Classify the customer inquiry as one of: billing, technical, account, general.")
    .outputs("category")
)
```

After `classifier` runs, `state["category"]` holds the response text (e.g., `"billing"`).

### Template variable substitution

Downstream agents reference state keys with `{key}` placeholders. ADK resolves these at runtime:

```python
handler = (
    Agent("handler", "gemini-2.5-flash")
    .instruct("The customer's issue is categorized as: {category}. Resolve it.")
)
```

When `handler` runs, `{category}` is replaced by whatever `classifier` stored.

### Pipeline example: classify then route

```python
from adk_fluent import Agent

pipeline = (
    Agent("classifier", "gemini-2.5-flash")
    .instruct("Classify the support ticket as: billing, technical, or account.")
    .outputs("category")
    >> Agent("resolver", "gemini-2.5-flash")
    .instruct(
        "You handle {category} issues. "
        "Investigate the customer's problem and provide a resolution."
    )
    .outputs("resolution")
    >> Agent("summarizer", "gemini-2.5-flash")
    .instruct("Summarize the resolution for the customer: {resolution}")
)
```

Each agent writes to a distinct key. The pipeline reads like a data flow: `category` feeds `resolver`, whose `resolution` feeds `summarizer`.

### Native ADK equivalent

Without adk-fluent, the same pattern requires manual wiring of `output_key` and building each agent individually:

```python
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent

classifier = LlmAgent(
    name="classifier",
    model="gemini-2.5-flash",
    instruction="Classify the support ticket as: billing, technical, or account.",
    output_key="category",
)

resolver = LlmAgent(
    name="resolver",
    model="gemini-2.5-flash",
    instruction=(
        "You handle {category} issues. "
        "Investigate the customer's problem and provide a resolution."
    ),
    output_key="resolution",
)

summarizer = LlmAgent(
    name="summarizer",
    model="gemini-2.5-flash",
    instruction="Summarize the resolution for the customer: {resolution}",
)

pipeline = SequentialAgent(
    name="support_pipeline",
    sub_agents=[classifier, resolver, summarizer],
)
```

## Typed Output: `.output_schema()` and `@ Schema`

When you need the LLM to return structured JSON rather than free text, use `.output_schema()` with a Pydantic model. The LLM is constrained to respond **only** with JSON matching the schema -- no prose, no markdown, just data.

```{important}
When `output_schema` is set, the agent **cannot use tools**. ADK enforces this because structured output mode changes how the model generates responses. If you need both tool use and structured output, split them into separate agents in a pipeline.
```

### Defining a Pydantic model

```python
from pydantic import BaseModel, Field

class Invoice(BaseModel):
    vendor: str = Field(description="Company or person who issued the invoice")
    amount: float = Field(description="Total amount in USD")
    due_date: str = Field(description="Due date in YYYY-MM-DD format")
    line_items: list[str] = Field(description="List of items or services billed")
```

Field descriptions are passed to the LLM as part of the schema, helping it fill fields accurately.

### Builder style: `.output_schema()`

```python
extractor = (
    Agent("invoice_extractor", "gemini-2.5-flash")
    .instruct("Extract invoice details from the provided document text.")
    .output_schema(Invoice)
    .outputs("invoice_data")
)
```

The agent will respond with a JSON object like:

```json
{
  "vendor": "Acme Corp",
  "amount": 1250.00,
  "due_date": "2026-03-15",
  "line_items": ["Consulting services", "Cloud hosting (Feb)"]
}
```

### Expression style: `@ Schema`

The `@` operator is shorthand for `.output_schema()`, designed for concise expression chains:

```python
extractor = (
    Agent("invoice_extractor", "gemini-2.5-flash")
    .instruct("Extract invoice details from the provided document text.")
    .outputs("invoice_data")
) @ Invoice
```

Both forms produce identical results. Use `@` in operator expressions where brevity matters; use `.output_schema()` in explicit builder chains where readability is the priority.

### Combining with `.outputs(key)`

When both `.output_schema()` and `.outputs(key)` are set, the structured JSON response is stored in session state under the given key. This is the recommended pattern for structured pipelines:

```python
from pydantic import BaseModel, Field
from adk_fluent import Agent

class SentimentResult(BaseModel):
    sentiment: str = Field(description="positive, negative, or neutral")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(description="Brief explanation of the classification")

analyzer = (
    Agent("sentiment_analyzer", "gemini-2.5-flash")
    .instruct("Analyze the sentiment of the provided customer review.")
    .output_schema(SentimentResult)
    .outputs("sentiment")
)
```

After this agent runs, `state["sentiment"]` contains the JSON string. Downstream agents can reference `{sentiment}` in their instructions.

### Native ADK equivalent

```python
from google.adk.agents.llm_agent import LlmAgent

extractor = LlmAgent(
    name="invoice_extractor",
    model="gemini-2.5-flash",
    instruction="Extract invoice details from the provided document text.",
    output_schema=Invoice,
    output_key="invoice_data",
)
```

## Input Schema: `.input_schema()`

`.input_schema()` defines the expected input structure when an agent is invoked as a tool by another agent. This is less commonly used than `output_schema`, but it matters in coordinator/delegate patterns where one agent calls another as a tool.

```python
from pydantic import BaseModel, Field
from adk_fluent import Agent

class LookupRequest(BaseModel):
    company_name: str = Field(description="Name of the company to look up")
    fields: list[str] = Field(description="Which data fields to retrieve")

class CompanyInfo(BaseModel):
    name: str
    industry: str
    revenue: str
    employee_count: int

lookup_agent = (
    Agent("company_lookup", "gemini-2.5-flash")
    .instruct("Look up the requested company information and return structured data.")
    .input_schema(LookupRequest)
    .output_schema(CompanyInfo)
)
```

When a coordinator agent delegates to `lookup_agent`, it knows what arguments to provide (`LookupRequest`) and what structured response to expect (`CompanyInfo`).

## State Access Patterns

### Reading structured data in instructions

The simplest pattern is `{key}` substitution. The entire value stored at that key is interpolated into the instruction string:

```python
pipeline = (
    Agent("extractor", "gemini-2.5-flash")
    .instruct("Extract the order details.")
    .output_schema(OrderDetails)
    .outputs("order")
    >> Agent("fulfillment", "gemini-2.5-flash")
    .instruct("Process this order for fulfillment: {order}")
)
```

The fulfillment agent receives the full JSON string in its instruction, which it can reason about.

### Programmatic state access in callbacks

For more complex logic, use callbacks to read and act on structured state:

```python
def log_high_value_orders(callback_context, llm_request):
    """Before-model callback that flags high-value orders."""
    order_json = callback_context.state.get("order", "{}")
    import json
    try:
        order = json.loads(order_json) if isinstance(order_json, str) else order_json
        if order.get("total", 0) > 10000:
            print(f"HIGH VALUE ORDER: {order.get('total')}")
    except (json.JSONDecodeError, TypeError):
        pass
    return None

fulfillment = (
    Agent("fulfillment", "gemini-2.5-flash")
    .instruct("Process this order: {order}")
    .before_model(log_high_value_orders)
)
```

### Programmatic state access in tool functions

Tool functions can also read structured data from the session state through the tool context:

```python
def check_inventory(item_name: str, tool_context) -> str:
    """Check inventory for an item, using order context from state."""
    order_json = tool_context.state.get("order", "{}")
    # Use order context to determine warehouse location, priority, etc.
    return f"Item '{item_name}' is in stock."

fulfillment = (
    Agent("fulfillment", "gemini-2.5-flash")
    .instruct("Process this order: {order}. Check inventory for each item.")
    .tool(check_inventory)
)
```

### Pattern: classifier drives deterministic routing

A common architecture pairs `.outputs()` with deterministic routing. The classifier stores its result, and a `Route` (or dict shorthand) branches without any additional LLM call:

```python
from adk_fluent import Agent
from adk_fluent._routing import Route

classifier = (
    Agent("classifier", "gemini-2.5-flash")
    .instruct("Classify the request as: refund, exchange, or inquiry.")
    .outputs("request_type")
)

refund_agent = Agent("refund", "gemini-2.5-flash").instruct("Process the refund request.")
exchange_agent = Agent("exchange", "gemini-2.5-flash").instruct("Process the exchange request.")
inquiry_agent = Agent("inquiry", "gemini-2.5-flash").instruct("Answer the customer inquiry.")

# Route on exact match -- zero LLM calls for routing
pipeline = classifier >> Route("request_type").eq(
    "refund", refund_agent
).eq(
    "exchange", exchange_agent
).eq(
    "inquiry", inquiry_agent
)

# Dict shorthand (equivalent)
pipeline = classifier >> {
    "refund": refund_agent,
    "exchange": exchange_agent,
    "inquiry": inquiry_agent,
}
```

## Complete Example

This example demonstrates a realistic document processing pipeline that combines all three mechanisms. An extractor agent parses contract documents into structured data. A risk assessor reads that data and produces a risk evaluation. A final agent summarizes everything for a human reviewer.

### Fluent version

```python
from pydantic import BaseModel, Field
from adk_fluent import Agent

# --- Schemas ---

class ContractDetails(BaseModel):
    parties: list[str] = Field(description="Names of all contracting parties")
    effective_date: str = Field(description="Contract start date, YYYY-MM-DD")
    termination_date: str = Field(description="Contract end date, YYYY-MM-DD")
    total_value: float = Field(description="Total contract value in USD")
    key_obligations: list[str] = Field(description="Major obligations of each party")
    governing_law: str = Field(description="Jurisdiction governing the contract")

class RiskAssessment(BaseModel):
    risk_level: str = Field(description="low, medium, or high")
    risk_factors: list[str] = Field(description="Identified risk factors")
    recommendation: str = Field(description="Action recommendation for legal review")

# --- Pipeline ---

pipeline = (
    # Step 1: Extract structured contract data
    Agent("extractor", "gemini-2.5-flash")
    .instruct(
        "Extract the key details from the provided contract document. "
        "Identify all parties, dates, financial terms, obligations, and jurisdiction."
    )
    .output_schema(ContractDetails)
    .outputs("contract")

    # Step 2: Assess risk based on extracted data
    >> Agent("risk_assessor", "gemini-2.5-flash")
    .instruct(
        "Review the following contract details and assess the risk level.\n\n"
        "Contract: {contract}\n\n"
        "Consider: value concentration, termination clauses, jurisdiction risks, "
        "and obligation imbalances."
    )
    .output_schema(RiskAssessment)
    .outputs("risk")

    # Step 3: Produce a human-readable summary
    >> Agent("summarizer", "gemini-2.5-flash")
    .instruct(
        "Write a concise executive summary for the legal team.\n\n"
        "Contract details: {contract}\n"
        "Risk assessment: {risk}\n\n"
        "Include the risk level, key concerns, and recommended next steps."
    )
)
```

### Native ADK equivalent

```python
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent

extractor = LlmAgent(
    name="extractor",
    model="gemini-2.5-flash",
    instruction=(
        "Extract the key details from the provided contract document. "
        "Identify all parties, dates, financial terms, obligations, and jurisdiction."
    ),
    output_schema=ContractDetails,
    output_key="contract",
)

risk_assessor = LlmAgent(
    name="risk_assessor",
    model="gemini-2.5-flash",
    instruction=(
        "Review the following contract details and assess the risk level.\n\n"
        "Contract: {contract}\n\n"
        "Consider: value concentration, termination clauses, jurisdiction risks, "
        "and obligation imbalances."
    ),
    output_schema=RiskAssessment,
    output_key="risk",
)

summarizer = LlmAgent(
    name="summarizer",
    model="gemini-2.5-flash",
    instruction=(
        "Write a concise executive summary for the legal team.\n\n"
        "Contract details: {contract}\n"
        "Risk assessment: {risk}\n\n"
        "Include the risk level, key concerns, and recommended next steps."
    ),
)

pipeline = SequentialAgent(
    name="contract_pipeline",
    sub_agents=[extractor, risk_assessor, summarizer],
)
```

The fluent version reads as a single expression with the data flow visible at a glance: `extractor` produces `contract`, `risk_assessor` reads `{contract}` and produces `risk`, and `summarizer` reads both. The native ADK version achieves the same result but requires assembling the pipeline separately from the agent definitions.

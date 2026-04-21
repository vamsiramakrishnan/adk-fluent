# Structured Data

Agents that return free-form text are fine for chat, but production pipelines need predictable data. A classifier must emit a category string that a router can branch on. An extraction step must produce a JSON object that a downstream formatter can render. adk-fluent provides three complementary mechanisms for structured data flow: storing output in session state, enforcing typed output schemas, and declaring input schemas for tool-invoked agents.

## Which one do I need?

Three methods, three different jobs. They compose — most production agents use two of them together.

```{mermaid}
flowchart LR
    in[incoming call] -->|.accepts Schema<br/>validates tool args| agent((agent))
    agent -->|.returns Schema<br/>JSON constraint<br/>on the LLM| out[response]
    out -->|.writes key<br/>persist to state| state[(state)]

    classDef in fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    classDef agent fill:#fff3e0,stroke:#e65100,color:#bf360c
    classDef state fill:#f3e5f5,stroke:#6a1b9a,color:#4a148c
    class in,out in
    class agent agent
    class state state
```

| Method | What it does | Runtime effect | Typical use |
|---|---|---|---|
| `.writes(key)` | Stores the agent's response in `state[key]` after it runs. | Side effect after response. Response itself unchanged. | Feeding output into downstream `{key}` templates. |
| `.returns(Schema)` | Constrains the LLM to emit JSON matching a Pydantic model. | Hard constraint on LLM output format. | Machine-readable responses; classifiers, extractors. |
| `.accepts(Schema)` | Validates the tool-call arguments when this agent is invoked as an `agent_tool`. | Input validation at tool invocation. | Agents consumed by other agents via `.delegate_to()`. |

:::{tip} Rule of thumb
If a downstream step reads it, **`.writes()`**. If the shape matters, **`.returns()`**. If a parent agent calls it like a tool, **`.accepts()`**. You can stack all three.
:::

:::{warning} `.returns()` disables tools
Structured-output mode and tool use are mutually exclusive in ADK. If you need both, split them: an extractor with `.returns()` followed by a worker with `.tool()`s reading the extracted state.
:::

## Storing Output in State: `.writes(key)`

`.writes(key)` is an alias for ADK's `output_key`. When an agent finishes, its response text is written to session state under the given key. Other agents can then read that value through template variable substitution in their instructions.

### Basic usage

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent

classifier = (
    Agent("classifier", "gemini-2.5-flash")
    .instruct("Classify the customer inquiry as one of: billing, technical, account, general.")
    .writes("category")
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent } from "adk-fluent-ts";

const classifier = new Agent("classifier", "gemini-2.5-flash")
  .instruct("Classify the customer inquiry as one of: billing, technical, account, general.")
  .writes("category");
```
:::
::::

After `classifier` runs, `state["category"]` holds the response text (e.g., `"billing"`).

### Template variable substitution

Downstream agents reference state keys with `{key}` placeholders. ADK resolves these at runtime:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
handler = (
    Agent("handler", "gemini-2.5-flash")
    .instruct("The customer's issue is categorized as: {category}. Resolve it.")
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const handler = new Agent("handler", "gemini-2.5-flash")
  .instruct("The customer's issue is categorized as: {category}. Resolve it.");
```
:::
::::

When `handler` runs, `{category}` is replaced by whatever `classifier` stored.

### Pipeline example: classify then route

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent

pipeline = (
    Agent("classifier", "gemini-2.5-flash")
    .instruct("Classify the support ticket as: billing, technical, or account.")
    .writes("category")
    >> Agent("resolver", "gemini-2.5-flash")
    .instruct(
        "You handle {category} issues. "
        "Investigate the customer's problem and provide a resolution."
    )
    .writes("resolution")
    >> Agent("summarizer", "gemini-2.5-flash")
    .instruct("Summarize the resolution for the customer: {resolution}")
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent } from "adk-fluent-ts";

const pipeline = new Agent("classifier", "gemini-2.5-flash")
  .instruct("Classify the support ticket as: billing, technical, or account.")
  .writes("category")
  .then(
    new Agent("resolver", "gemini-2.5-flash")
      .instruct(
        "You handle {category} issues. " +
        "Investigate the customer's problem and provide a resolution.",
      )
      .writes("resolution"),
  )
  .then(
    new Agent("summarizer", "gemini-2.5-flash")
      .instruct("Summarize the resolution for the customer: {resolution}"),
  );
```
:::
::::

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

## Typed Output: `.returns()` and `@ Schema`

When you need the LLM to return structured JSON rather than free text, use `.returns()` with a Pydantic model. The LLM is constrained to respond **only** with JSON matching the schema -- no prose, no markdown, just data.

```{important}
When `output_schema` is set, the agent **cannot use tools**. ADK enforces this because structured output mode changes how the model generates responses. If you need both tool use and structured output, split them into separate agents in a pipeline.
```

### Defining a schema

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from pydantic import BaseModel, Field

class Invoice(BaseModel):
    vendor: str = Field(description="Company or person who issued the invoice")
    amount: float = Field(description="Total amount in USD")
    due_date: str = Field(description="Due date in YYYY-MM-DD format")
    line_items: list[str] = Field(description="List of items or services billed")
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
// Option 1: Plain JSON Schema (as const)
const InvoiceSchema = {
  type: "object",
  properties: {
    vendor: { type: "string", description: "Company or person who issued the invoice" },
    amount: { type: "number", description: "Total amount in USD" },
    due_date: { type: "string", description: "Due date in YYYY-MM-DD format" },
    line_items: {
      type: "array",
      items: { type: "string" },
      description: "List of items or services billed",
    },
  },
  required: ["vendor", "amount", "due_date", "line_items"],
} as const;

// Option 2: Zod (if you prefer runtime validation)
// import { z } from "zod";
// const Invoice = z.object({
//   vendor: z.string().describe("Company or person who issued the invoice"),
//   amount: z.number().describe("Total amount in USD"),
//   due_date: z.string().describe("Due date in YYYY-MM-DD format"),
//   line_items: z.array(z.string()),
// });
```
:::
::::

Field descriptions are passed to the LLM as part of the schema, helping it fill fields accurately.

### Builder style: `.returns()` / `.outputAs()`

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
extractor = (
    Agent("invoice_extractor", "gemini-2.5-flash")
    .instruct("Extract invoice details from the provided document text.")
    .returns(Invoice)
    .writes("invoice_data")
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const extractor = new Agent("invoice_extractor", "gemini-2.5-flash")
  .instruct("Extract invoice details from the provided document text.")
  .outputAs(InvoiceSchema)
  .writes("invoice_data");
```
:::
::::

:::{note} TypeScript naming
TypeScript uses `.outputAs(schema)` where Python uses `.returns(Model)`. It accepts any JSON schema descriptor (plain `as const` objects, Zod schemas, or native JSON schema). The `@` operator shorthand is Python-only.
:::

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

The `@` operator is shorthand for `.returns()`, designed for concise expression chains:

```python
extractor = (
    Agent("invoice_extractor", "gemini-2.5-flash")
    .instruct("Extract invoice details from the provided document text.")
    .writes("invoice_data")
) @ Invoice
```

Both forms produce identical results. Use `@` in operator expressions where brevity matters; use `.returns()` in explicit builder chains where readability is the priority.

### Combining with `.writes(key)`

When both `.returns()` / `.outputAs()` and `.writes(key)` are set, the structured JSON response is stored in session state under the given key. This is the recommended pattern for structured pipelines:

::::{tab-set}
:::{tab-item} Python
:sync: python

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
    .returns(SentimentResult)
    .writes("sentiment")
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent } from "adk-fluent-ts";

const SentimentResultSchema = {
  type: "object",
  properties: {
    sentiment: { type: "string", description: "positive, negative, or neutral" },
    confidence: { type: "number", description: "Confidence score between 0.0 and 1.0" },
    reasoning: { type: "string", description: "Brief explanation of the classification" },
  },
  required: ["sentiment", "confidence", "reasoning"],
} as const;

const analyzer = new Agent("sentiment_analyzer", "gemini-2.5-flash")
  .instruct("Analyze the sentiment of the provided customer review.")
  .outputAs(SentimentResultSchema)
  .writes("sentiment");
```
:::
::::

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

## Input Schema: `.accepts()`

`.accepts()` defines the expected input structure when an agent is invoked as a tool by another agent. This is less commonly used than `returns`, but it matters in coordinator/agent_tool patterns where one agent calls another as a tool.

::::{tab-set}
:::{tab-item} Python
:sync: python

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
    .accepts(LookupRequest)
    .returns(CompanyInfo)
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent } from "adk-fluent-ts";

const LookupRequestSchema = {
  type: "object",
  properties: {
    company_name: { type: "string", description: "Name of the company to look up" },
    fields: { type: "array", items: { type: "string" } },
  },
  required: ["company_name", "fields"],
} as const;

const CompanyInfoSchema = {
  type: "object",
  properties: {
    name: { type: "string" },
    industry: { type: "string" },
    revenue: { type: "string" },
    employee_count: { type: "number" },
  },
  required: ["name", "industry", "revenue", "employee_count"],
} as const;

const lookupAgent = new Agent("company_lookup", "gemini-2.5-flash")
  .instruct("Look up the requested company information and return structured data.")
  .accepts(LookupRequestSchema)
  .outputAs(CompanyInfoSchema);
```
:::
::::

When a coordinator agent invokes `lookup_agent` as an agent_tool, it knows what arguments to provide (`LookupRequest`) and what structured response to expect (`CompanyInfo`).

## State Access Patterns

### Reading structured data in instructions

The simplest pattern is `{key}` substitution. The entire value stored at that key is interpolated into the instruction string:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
pipeline = (
    Agent("extractor", "gemini-2.5-flash")
    .instruct("Extract the order details.")
    .returns(OrderDetails)
    .writes("order")
    >> Agent("fulfillment", "gemini-2.5-flash")
    .instruct("Process this order for fulfillment: {order}")
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const pipeline = new Agent("extractor", "gemini-2.5-flash")
  .instruct("Extract the order details.")
  .outputAs(OrderDetailsSchema)
  .writes("order")
  .then(
    new Agent("fulfillment", "gemini-2.5-flash")
      .instruct("Process this order for fulfillment: {order}"),
  );
```
:::
::::

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

A common architecture pairs `.writes()` with deterministic routing. The classifier stores its result, and a `Route` (or dict shorthand) branches without any additional LLM call:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, Route

classifier = (
    Agent("classifier", "gemini-2.5-flash")
    .instruct("Classify the request as: refund, exchange, or inquiry.")
    .writes("request_type")
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
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, Route } from "adk-fluent-ts";

const classifier = new Agent("classifier", "gemini-2.5-flash")
  .instruct("Classify the request as: refund, exchange, or inquiry.")
  .writes("request_type");

const refundAgent = new Agent("refund", "gemini-2.5-flash").instruct("Process the refund request.");
const exchangeAgent = new Agent("exchange", "gemini-2.5-flash").instruct("Process the exchange request.");
const inquiryAgent = new Agent("inquiry", "gemini-2.5-flash").instruct("Answer the customer inquiry.");

// Route on exact match -- zero LLM calls for routing
const pipeline = classifier.then(
  new Route("request_type")
    .eq("refund", refundAgent)
    .eq("exchange", exchangeAgent)
    .eq("inquiry", inquiryAgent),
);
```
:::
::::

## Complete Example

This example demonstrates a realistic document processing pipeline that combines all three mechanisms. An extractor agent parses contract documents into structured data. A risk assessor reads that data and produces a risk evaluation. A final agent summarizes everything for a human reviewer.

### Fluent version

::::{tab-set}
:::{tab-item} Python
:sync: python

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
    .returns(ContractDetails)
    .writes("contract")

    # Step 2: Assess risk based on extracted data
    >> Agent("risk_assessor", "gemini-2.5-flash")
    .instruct(
        "Review the following contract details and assess the risk level.\n\n"
        "Contract: {contract}\n\n"
        "Consider: value concentration, termination clauses, jurisdiction risks, "
        "and obligation imbalances."
    )
    .returns(RiskAssessment)
    .writes("risk")

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
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent } from "adk-fluent-ts";

// --- Schemas ---

const ContractDetailsSchema = {
  type: "object",
  properties: {
    parties: { type: "array", items: { type: "string" }, description: "Names of all contracting parties" },
    effective_date: { type: "string", description: "Contract start date, YYYY-MM-DD" },
    termination_date: { type: "string", description: "Contract end date, YYYY-MM-DD" },
    total_value: { type: "number", description: "Total contract value in USD" },
    key_obligations: { type: "array", items: { type: "string" } },
    governing_law: { type: "string", description: "Jurisdiction governing the contract" },
  },
  required: ["parties", "effective_date", "termination_date", "total_value", "key_obligations", "governing_law"],
} as const;

const RiskAssessmentSchema = {
  type: "object",
  properties: {
    risk_level: { type: "string", description: "low, medium, or high" },
    risk_factors: { type: "array", items: { type: "string" } },
    recommendation: { type: "string", description: "Action recommendation for legal review" },
  },
  required: ["risk_level", "risk_factors", "recommendation"],
} as const;

// --- Pipeline ---

const pipeline = new Agent("extractor", "gemini-2.5-flash")
  .instruct(
    "Extract the key details from the provided contract document. " +
    "Identify all parties, dates, financial terms, obligations, and jurisdiction.",
  )
  .outputAs(ContractDetailsSchema)
  .writes("contract")
  .then(
    new Agent("risk_assessor", "gemini-2.5-flash")
      .instruct(
        "Review the following contract details and assess the risk level.\n\n" +
        "Contract: {contract}\n\n" +
        "Consider: value concentration, termination clauses, jurisdiction risks, " +
        "and obligation imbalances.",
      )
      .outputAs(RiskAssessmentSchema)
      .writes("risk"),
  )
  .then(
    new Agent("summarizer", "gemini-2.5-flash")
      .instruct(
        "Write a concise executive summary for the legal team.\n\n" +
        "Contract details: {contract}\n" +
        "Risk assessment: {risk}\n\n" +
        "Include the risk level, key concerns, and recommended next steps.",
      ),
  );
```
:::
::::

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

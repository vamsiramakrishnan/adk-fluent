# Framework Comparison

How adk-fluent compares to LangGraph, CrewAI, and native ADK for common agent patterns.

## Feature Matrix

| Feature              | LangGraph                  | CrewAI            | Native ADK       | adk-fluent            |
| -------------------- | -------------------------- | ----------------- | ---------------- | --------------------- |
| Lines per agent      | 15-25                      | 10-15             | 8-15             | 1-3                   |
| Pipeline composition | StateGraph + edges         | Crew sequential   | SequentialAgent  | `>>` operator         |
| Parallel execution   | Fan-out nodes + edges      | Crew parallel     | ParallelAgent    | `\|` operator         |
| Conditional routing  | conditional_edges          | N/A (LLM decides) | Custom BaseAgent | `Route()` builder     |
| Loops                | Conditional back-edges     | N/A               | LoopAgent        | `* N` or `* until()`  |
| Typed output         | Pydantic via output_parser | Pydantic          | output_schema    | `@ Schema`            |
| Built-in testing     | No                         | No                | No               | `.mock()`, `.test()`  |
| IDE autocomplete     | Partial                    | Partial           | Yes              | Yes (typed stubs)     |
| Visualization        | LangGraph Studio           | No                | No               | `.explain()`, Mermaid |
| Streaming            | Yes                        | No                | Yes              | `.stream()`           |
| State management     | TypedDict                  | Shared memory     | Session state    | `S.*` module          |
| Result type          | LangGraph Runnable         | CrewOutput        | ADK Agent        | ADK Agent (native)    |

## Pattern 1: Document Processing Pipeline

A contract review system: extract key terms, analyze legal risks, produce an executive summary.

### LangGraph

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

class ContractState(TypedDict):
    document: str
    terms: str
    risks: str
    summary: str

def extract_terms(state: ContractState) -> dict:
    # Call LLM to extract key terms
    result = llm.invoke(
        "Extract key terms from the contract: parties, dates, payment terms, "
        "termination clauses.\n\n" + state["document"]
    )
    return {"terms": result.content}

def analyze_risks(state: ContractState) -> dict:
    result = llm.invoke(
        "Analyze these terms for legal risks. Flag unusual clauses, "
        "missing protections, liability concerns.\n\n" + state["terms"]
    )
    return {"risks": result.content}

def summarize(state: ContractState) -> dict:
    result = llm.invoke(
        "Produce a one-page executive summary combining the extracted "
        "terms and risk analysis. Use clear, non-legal language.\n\n"
        f"Terms: {state['terms']}\nRisks: {state['risks']}"
    )
    return {"summary": result.content}

graph = StateGraph(ContractState)
graph.add_node("extract", extract_terms)
graph.add_node("analyze", analyze_risks)
graph.add_node("summarize", summarize)
graph.add_edge(START, "extract")
graph.add_edge("extract", "analyze")
graph.add_edge("analyze", "summarize")
graph.add_edge("summarize", END)

app = graph.compile()
# ~35 lines of setup
```

### CrewAI

```python
from crewai import Agent, Task, Crew

extractor = Agent(
    role="Contract Analyst",
    goal="Extract key terms from contracts",
    backstory="You are a legal document analyst specializing in contract review.",
    llm="gemini/gemini-2.5-flash",
)

analyst = Agent(
    role="Risk Assessor",
    goal="Identify legal risks in contract terms",
    backstory="You are a legal risk specialist with 20 years experience.",
    llm="gemini/gemini-2.5-flash",
)

summarizer = Agent(
    role="Executive Writer",
    goal="Produce clear executive summaries",
    backstory="You translate legal analysis into plain language.",
    llm="gemini/gemini-2.5-flash",
)

tasks = [
    Task(description="Extract key terms: parties, dates, payment, termination.", agent=extractor),
    Task(description="Analyze extracted terms for legal risks.", agent=analyst),
    Task(description="Write a one-page executive summary.", agent=summarizer),
]

crew = Crew(agents=[extractor, analyst, summarizer], tasks=tasks, process="sequential")
result = crew.kickoff()
# ~30 lines, but each agent needs role + goal + backstory
```

### Native ADK

```python
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent

extractor = LlmAgent(
    name="extractor",
    model="gemini-2.5-flash",
    instruction=(
        "Extract key terms from the contract: parties involved, "
        "effective dates, payment terms, and termination clauses."
    ),
)
analyst = LlmAgent(
    name="risk_analyst",
    model="gemini-2.5-flash",
    instruction=(
        "Analyze the extracted terms for legal risks. Flag any "
        "unusual clauses, missing protections, or liability concerns."
    ),
)
summarizer = LlmAgent(
    name="summarizer",
    model="gemini-2.5-flash",
    instruction=(
        "Produce a one-page executive summary combining the extracted "
        "terms and risk analysis. Use clear, non-legal language."
    ),
)
pipeline = SequentialAgent(
    name="contract_review",
    description="Extract, analyze, and summarize contracts",
    sub_agents=[extractor, analyst, summarizer],
)
# ~20 lines -- clean but verbose for the topology complexity
```

### adk-fluent

```python
from adk_fluent import Agent

extractor = Agent("extractor", "gemini-2.5-flash").instruct(
    "Extract key terms: parties, dates, payment terms, termination clauses."
)
analyst = Agent("risk_analyst", "gemini-2.5-flash").instruct(
    "Analyze extracted terms for legal risks."
)
summarizer = Agent("summarizer", "gemini-2.5-flash").instruct(
    "Produce a one-page executive summary in plain language."
)

pipeline = extractor >> analyst >> summarizer
# 4 lines of agent definition + 1 line of composition
# Result: native SequentialAgent -- same as hand-built
```

**Line count: LangGraph ~35 | CrewAI ~30 | Native ADK ~20 | adk-fluent ~5**

[See cookbook example](https://github.com/vamsiramakrishnan/adk-fluent/blob/master/examples/cookbook/04_sequential_pipeline.py)

## Pattern 2: Multi-Source Research with Quality Loop

Decompose a query, search 3 sources in parallel, synthesize findings, review quality in a loop, and produce a typed report.

### LangGraph

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

class ResearchState(TypedDict):
    query: str
    web_results: str
    academic_results: str
    news_results: str
    synthesis: str
    quality_score: float

def analyze_query(state): ...
def search_web(state): ...
def search_academic(state): ...
def search_news(state): ...
def synthesize(state): ...
def review_quality(state): ...
def revise(state): ...

def should_continue(state):
    return "revise" if state["quality_score"] < 0.85 else "report"

graph = StateGraph(ResearchState)
graph.add_node("analyze", analyze_query)
graph.add_node("search_web", search_web)
graph.add_node("search_academic", search_academic)
graph.add_node("search_news", search_news)
graph.add_node("synthesize", synthesize)
graph.add_node("review", review_quality)
graph.add_node("revise", revise)
graph.add_node("report", write_report)
graph.add_edge(START, "analyze")
graph.add_edge("analyze", "search_web")
graph.add_edge("analyze", "search_academic")
graph.add_edge("analyze", "search_news")
graph.add_edge("search_web", "synthesize")
graph.add_edge("search_academic", "synthesize")
graph.add_edge("search_news", "synthesize")
graph.add_edge("synthesize", "review")
graph.add_conditional_edges("review", should_continue)
graph.add_edge("revise", "review")
graph.add_edge("report", END)
app = graph.compile()
# ~55 lines of graph wiring -- the topology IS the code
```

### adk-fluent

```python
from adk_fluent import Agent, S, C

analyzer = Agent("analyzer", MODEL).instruct("Decompose the query into sub-questions.").writes("plan")
web = Agent("web", MODEL).instruct("Search web sources.").context(C.from_state("plan")).writes("web_results")
papers = Agent("papers", MODEL).instruct("Search academic papers.").context(C.from_state("plan")).writes("academic_results")
news = Agent("news", MODEL).instruct("Search recent news.").context(C.from_state("plan")).writes("news_results")
synthesizer = Agent("synth", MODEL).instruct("Synthesize findings.").writes("synthesis")
reviewer = Agent("reviewer", MODEL).instruct("Score quality 0-1.").writes("quality_score")
reviser = Agent("reviser", MODEL).instruct("Revise based on feedback.").writes("synthesis")
writer = Agent("writer", MODEL).instruct("Write final report.") @ ResearchReport

research = (
    analyzer
    >> (web | papers | news)
    >> synthesizer
    >> (reviewer >> reviser) * until(lambda s: float(s.get("quality_score", 0)) >= 0.85)
    >> writer
)
# 9 lines of agents + 1 expression for the full topology
# Parallel search, quality loop, typed output -- all in one expression
```

**Line count: LangGraph ~55 | Native ADK ~45 | adk-fluent ~10**

[See cookbook example](https://github.com/vamsiramakrishnan/adk-fluent/blob/master/examples/cookbook/55_deep_research.py)

## Pattern 3: Customer Support Triage

Classify customer intent and route to the right specialist team.

### LangGraph

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

class SupportState(TypedDict):
    message: str
    intent: str
    response: str

def classify(state):
    result = llm.invoke("Classify intent: billing, technical, or general.\n\n" + state["message"])
    return {"intent": result.content.strip()}

def handle_billing(state):
    result = llm.invoke("You are a billing specialist. Help with: " + state["message"])
    return {"response": result.content}

def handle_technical(state):
    result = llm.invoke("You are tech support. Diagnose: " + state["message"])
    return {"response": result.content}

def handle_general(state):
    result = llm.invoke("You are general support. Help with: " + state["message"])
    return {"response": result.content}

def route_intent(state):
    return state["intent"]

graph = StateGraph(SupportState)
graph.add_node("classify", classify)
graph.add_node("billing", handle_billing)
graph.add_node("technical", handle_technical)
graph.add_node("general", handle_general)
graph.add_edge(START, "classify")
graph.add_conditional_edges(
    "classify", route_intent,
    {"billing": "billing", "technical": "technical", "general": "general"},
)
graph.add_edge("billing", END)
graph.add_edge("technical", END)
graph.add_edge("general", END)
app = graph.compile()
# ~40 lines -- routing requires conditional_edges + routing function
```

### adk-fluent

```python
from adk_fluent import Agent, S, C
from adk_fluent._routing import Route

classifier = Agent("classifier", MODEL).instruct(
    "Classify intent: billing, technical, or general.\nMessage: {message}"
).context(C.none()).writes("intent")

billing = Agent("billing", MODEL).instruct("Help with billing issues.")
technical = Agent("technical", MODEL).instruct("Diagnose technical issues.")
general = Agent("general", MODEL).instruct("Handle general inquiries.")

support = (
    S.capture("message")
    >> classifier
    >> Route("intent")
        .eq("billing", billing)
        .eq("technical", technical)
        .otherwise(general)
)
# 8 lines of agents + 1 routing expression
# Route() replaces conditional_edges + routing function
```

**Line count: LangGraph ~40 | Native ADK ~35 | adk-fluent ~8**

[See cookbook example](https://github.com/vamsiramakrishnan/adk-fluent/blob/master/examples/cookbook/56_customer_support_triage.py)

## When to Use Each Framework

### Use LangGraph when

- You need fine-grained control over graph execution and state transitions
- Your workflow has complex conditional paths that don't map to sequential/parallel/routing patterns
- You want LangGraph Studio for visual debugging
- You're already invested in the LangChain ecosystem

### Use CrewAI when

- You want role-based agent personas with rich backstories
- Your workflow is primarily sequential with LLM-driven task delegation
- You prefer a higher-level abstraction over graph construction

### Use native ADK when

- You need custom `BaseAgent` subclasses with `_run_async_impl`
- You're building framework-level tooling around ADK
- You need direct access to ADK internals not exposed through builders

### Use adk-fluent when

- You want the shortest path from idea to working agent topology
- You need to compose pipelines, fan-out, loops, and routing declaratively
- You want `.mock()` and `.test()` for deterministic testing without API calls
- You want to produce native ADK objects compatible with `adk web`, `adk run`, and `adk deploy`
- You want IDE autocomplete and type checking during development

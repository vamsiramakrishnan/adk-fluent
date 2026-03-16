"""
Knowledge Retrieval: Primary API + Fallback Search with // Operator

Pipeline topologies:
    //  vector_db // fulltext_search          (two-way fallback)
    //  internal_kb // web_search // expert   (three-way cascade)

    RAG pipeline:
        query_rewriter >> ( vector_db // fulltext ) >> answer_generator

Converted from cookbook example: 32_fallback_operator.py

Usage:
    cd examples
    adk web fallback_operator
"""

from adk_fluent import Agent, Pipeline
from adk_fluent._base import _FallbackBuilder
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# // creates a fallback chain — first success wins.
# In a knowledge retrieval system: try the fast vector DB first,
# fall back to full-text search if vectors miss.
vector_search = (
    Agent("vector_db")
    .model("gemini-2.0-flash")
    .instruct("Query the vector database for semantically similar documents.")
)
fulltext_search = (
    Agent("fulltext_search")
    .model("gemini-2.5-flash")
    .instruct("Perform full-text search across the document corpus with BM25 ranking.")
)

retrieval = vector_search // fulltext_search  # Try vector first, fall back to fulltext

# Three-way fallback — enterprise knowledge retrieval with graceful degradation
internal_kb = (
    Agent("internal_kb")
    .model("gemini-2.0-flash")
    .instruct("Search the internal company knowledge base for relevant articles.")
)
web_search = (
    Agent("web_search")
    .model("gemini-2.5-flash")
    .instruct("Search the public web for relevant technical documentation.")
)
expert_consult = (
    Agent("expert_system")
    .model("gemini-2.5-pro")
    .instruct("Use expert reasoning to synthesize an answer from first principles.")
)

resilient_retrieval = internal_kb // web_search // expert_consult

# Composes with >> in pipelines — retrieval is one step in a larger RAG pipeline
rag_pipeline = (
    Agent("query_rewriter").model("gemini-2.5-flash").instruct("Rewrite the user query for optimal retrieval.")
    >> (vector_search // fulltext_search)
    >> Agent("answer_generator").model("gemini-2.5-flash").instruct("Generate an answer using the retrieved context.")
)

# Composes with | in parallel — search multiple domains simultaneously
legal_retrieval = Agent("case_law_db").model("gemini-2.0-flash") // Agent("statute_search").model("gemini-2.5-pro")
regulatory_retrieval = Agent("reg_db").model("gemini-2.0-flash") // Agent("federal_register").model("gemini-2.5-pro")
parallel_legal = legal_retrieval | regulatory_retrieval

# // works with functions too — static fallback for when all LLMs fail
fallback_with_default = Agent("primary_search").model("gemini-2.5-flash").instruct("Search for the answer.") // (
    lambda s: {"result": "No results found. Please contact support."}
)

root_agent = fallback_with_default.build()

/**
 * 02 — Agent with Tools
 *
 * Knowledge-base lookup agent. Demonstrates `.tool()` and `.tools()` for
 * attaching plain functions to an LLM agent. The TS adapter wraps callables
 * inside the underlying ADK `FunctionTool` at build time.
 */
import assert from "node:assert/strict";
import { Agent, T } from "../../src/index.js";

function searchDocs(query: string): { hits: string[] } {
  // Pretend we hit a vector store. The body doesn't matter for the cookbook —
  // what matters is that the LLM sees the function as a tool.
  return { hits: [`doc about ${query}`] };
}

function lookupTicket(id: string): { id: string; status: string } {
  return { id, status: "open" };
}

const agent = new Agent("support", "gemini-2.5-flash")
  .instruct("Use the available tools to answer support questions.")
  .tool(searchDocs)
  .tool(lookupTicket)
  .build() as Record<string, unknown>;

const tools = agent.tools as unknown[];
assert.equal(tools.length, 2);

// Same agent, but composed via the T namespace (chained instead of repeated
// .tool() calls). T.fn(...) wraps a callable as a TComposite that the
// builder can spread into the tool list.
const agent2 = new Agent("support2", "gemini-2.5-flash")
  .instruct("Use the available tools to answer support questions.")
  .tools(T.fn(searchDocs))
  .tools(T.fn(lookupTicket))
  .build() as Record<string, unknown>;

assert.equal((agent2.tools as unknown[]).length, 2);

export { agent, agent2 };

# Zed Setup

Set up [Zed](https://zed.dev) to generate idiomatic adk-fluent and Google ADK code.

## 1. Quick use — llms.txt

Reference adk-fluent's documentation directly in Zed's assistant chat:

```
#fetch https://vamsiramakrishnan.github.io/adk-fluent/llms.txt
```

This loads the full adk-fluent API reference, patterns, and best practices into the conversation context.

## 2. MCP server — live documentation access

Open Zed Settings and add an MCP context server.

### Option A: adk-fluent GitMCP (free)

Add to your Zed settings (`settings.json`):

```json
{
  "context_servers": {
    "adk-fluent": {
      "command": {
        "label": "adk-fluent docs",
        "path": "npx",
        "args": ["-y", "@anthropic-ai/mcp-proxy", "--transport", "http", "https://gitmcp.io/vamsiramakrishnan/adk-fluent"]
      }
    }
  }
}
```

### Option B: Context7 MCP

```json
{
  "context_servers": {
    "context7": {
      "command": {
        "path": "npx",
        "args": ["-y", "@upstash/context7-mcp"]
      }
    }
  }
}
```

**Usage** — append `use context7` to your prompt:

```
Build me a pipeline with a researcher and writer agent using adk-fluent. use context7
```

## 3. Verify the setup

After configuring the MCP server, test it with a prompt like:

```
Create an adk-fluent agent that classifies customer support tickets
into categories, then routes them to specialized handler agents.
Use a FanOut for parallel processing and write results to state.
```

Zed should:
- Import from `adk_fluent` (not internal modules)
- Use the fluent builder pattern with method chaining
- Call `.build()` to produce native ADK objects
- Use `.writes()` for state management

# Cline Setup

Set up [Cline](https://github.com/cline/cline) (VS Code extension) to generate idiomatic adk-fluent and Google ADK code.

## 1. Project rules

Cline reads rules from `.clinerules/` in your project root.

### If you cloned the repo

The file is already generated at `.clinerules/adk-fluent.md`. Nothing to do.

### If you installed via pip

Download the rules file into your project:

```bash
curl -L https://raw.githubusercontent.com/vamsiramakrishnan/adk-fluent/master/.clinerules/adk-fluent.md \
  --create-dirs -o .clinerules/adk-fluent.md
```

## 2. MCP server — live documentation access

### Option A: adk-fluent GitMCP (free)

Add to your Cline MCP settings (`cline_mcp_settings.json`):

```json
{
  "mcpServers": {
    "adk-fluent": {
      "type": "sse",
      "url": "https://gitmcp.io/vamsiramakrishnan/adk-fluent"
    }
  }
}
```

### Option B: Context7 MCP

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"]
    }
  }
}
```

**Usage** — append `use context7` to your prompt:

```
Build me a pipeline with a researcher and writer agent using adk-fluent. use context7
```

## 3. Verify the setup

After adding the rules file and MCP server, test it with a prompt like:

```
Create an adk-fluent agent that classifies customer support tickets
into categories, then routes them to specialized handler agents.
Use a FanOut for parallel processing and write results to state.
```

Cline should:
- Import from `adk_fluent` (not internal modules)
- Use the fluent builder pattern with method chaining
- Call `.build()` to produce native ADK objects
- Use `.writes()` for state management

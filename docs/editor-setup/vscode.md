# VS Code (Copilot) Setup

Set up [GitHub Copilot](https://github.com/features/copilot) in VS Code to generate idiomatic adk-fluent and Google ADK code.

## 1. Project instructions

VS Code Copilot reads instructions from `.github/instructions/` in your project root.

```bash
curl -L https://raw.githubusercontent.com/vamsiramakrishnan/adk-fluent/master/CLAUDE.md \
  --create-dirs -o .github/instructions/adk-fluent.instructions.md
```

Copilot will automatically include these instructions when generating code in your project.

## 2. MCP server — live documentation access

VS Code supports MCP servers through `.vscode/mcp.json`. This gives Copilot on-demand access to adk-fluent documentation.

### Option A: adk-fluent GitMCP (free)

Create `.vscode/mcp.json` in your project:

```json
{
  "servers": {
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
  "servers": {
    "context7": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"]
    }
  }
}
```

## 3. Verify the setup

After adding the instructions file and MCP server, test in Copilot Chat:

```
Create an adk-fluent agent that classifies customer support tickets
into categories, then routes them to specialized handler agents.
Use a FanOut for parallel processing and write results to state.
```

Copilot should:
- Import from `adk_fluent` (not internal modules)
- Use the fluent builder pattern with method chaining
- Call `.build()` to produce native ADK objects
- Use `.writes()` for state management

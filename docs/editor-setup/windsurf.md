# Windsurf Setup

Set up [Windsurf](https://codeium.com/windsurf) to generate idiomatic adk-fluent and Google ADK code.

## 1. Project rules — `.windsurfrules`

Windsurf reads a `.windsurfrules` file from your project root.

```bash
curl -L https://raw.githubusercontent.com/vamsiramakrishnan/adk-fluent/master/CLAUDE.md \
  -o .windsurfrules
```

Windsurf will automatically include these rules when generating code in your project.

## 2. MCP server — live documentation access

Windsurf supports MCP servers for live documentation access. Open Settings and navigate to the MCP configuration.

### adk-fluent GitMCP (free)

Add the following MCP server configuration:

```json
{
  "mcpServers": {
    "adk-fluent": {
      "serverUrl": "https://gitmcp.io/vamsiramakrishnan/adk-fluent"
    }
  }
}
```

No authentication required. Windsurf will automatically have access to all adk-fluent documentation.

## 3. Verify the setup

After adding the rules file and MCP server, test it with a prompt like:

```
Create an adk-fluent agent that classifies customer support tickets
into categories, then routes them to specialized handler agents.
Use a FanOut for parallel processing and write results to state.
```

Windsurf should:
- Import from `adk_fluent` (not internal modules)
- Use the fluent builder pattern with method chaining
- Call `.build()` to produce native ADK objects
- Use `.writes()` for state management

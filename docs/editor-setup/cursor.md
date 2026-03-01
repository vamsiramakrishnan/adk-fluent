# Cursor Setup

Set up [Cursor](https://cursor.sh) to generate idiomatic adk-fluent and Google ADK code.

## 1. Project rules

Cursor reads rules from `.cursor/rules/` in your project root. Create a rules file to teach Cursor about adk-fluent patterns.

### Quick setup

```bash
curl -L https://raw.githubusercontent.com/vamsiramakrishnan/adk-fluent/master/CLAUDE.md \
  --create-dirs -o .cursor/rules/adk-fluent.mdc
```

### Custom docs (optional)

You can also add adk-fluent's documentation site as a custom docs source:

1. Open Cursor Settings
2. Go to **Features > Docs**
3. Click **Add new custom docs**
4. Enter: `https://vamsiramakrishnan.github.io/adk-fluent/`

Then reference it in chat with `@docs`.

## 2. MCP server — live documentation access

MCP servers give Cursor on-demand access to the full adk-fluent documentation.

### Option A: adk-fluent GitMCP (free)

Uses [GitMCP](https://gitmcp.io) to serve documentation directly from the GitHub repository.

::::{tab-set}
:::{tab-item} Automatic

```bash
npx -y @anthropic-ai/cursor-mcp-installer --transport http --url https://gitmcp.io/vamsiramakrishnan/adk-fluent adk-fluent
```

:::
:::{tab-item} Manual

Add to `~/.cursor/mcp.json`:

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

:::
::::

### Option B: Context7 MCP

Add to `~/.cursor/mcp.json`:

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

Cursor should:
- Import from `adk_fluent` (not internal modules)
- Use the fluent builder pattern with method chaining
- Call `.build()` to produce native ADK objects
- Use `.writes()` for state management

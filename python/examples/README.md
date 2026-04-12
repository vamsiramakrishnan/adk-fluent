# adk-fluent Examples

Self-contained guide to running every cookbook example — via CLI, `adk web`, or the visual cookbook runner.

## Setup from Scratch

```bash
# 1. Clone the repository
git clone https://github.com/vamsiramakrishnan/adk-fluent.git
cd adk-fluent

# 2. Install dependencies (pick one)
pip install -e ".[a2a,yaml,rich]"       # pip
uv sync --all-extras                    # uv (recommended)

# 3. Install just (task runner) — optional but convenient
# macOS: brew install just
# Linux: cargo install just  (or see https://github.com/casey/just#installation)

# 4. Configure credentials
cp examples/.env.example examples/.env
# Edit examples/.env with your API key (see below)
```

## Credentials

Two auth paths are supported. Pick **one**:

### Option A: Gemini API Key (simplest)

No GCP project needed. Get a free key at https://aistudio.google.com/app/apikey

```bash
# examples/.env
GOOGLE_API_KEY=your-gemini-api-key-here
```

### Option B: Vertex AI (full GCP)

Required for some advanced features (grounding, enterprise search, etc.).

```bash
# examples/.env
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=TRUE
```

## Folder Structure

```
examples/
├── .env.example          # Credentials template (copy to .env)
├── .env                  # Your credentials (git-ignored)
├── README.md             # This file
├── cookbook/              # 68 annotated cookbook files (pytest-runnable)
│   ├── 01_simple_agent.py
│   ├── 02_agent_with_tools.py
│   └── ...
├── simple_agent/         # Generated adk-web agent folders
│   ├── agent.py          # Entry point for `adk web`
│   └── __init__.py
├── weather_agent/
│   ├── agent.py
│   └── __init__.py
└── ...                   # 73 agent folders total
```

## Running Examples

### Option 1: `adk web` (ADK's built-in web UI)

```bash
cd examples
adk web simple_agent              # Basic agent
adk web weather_agent             # Agent with tools
adk web research_team             # Multi-agent pipeline
adk web operator_composition      # >> | * operators
adk web state_transforms          # S namespace
adk web route_branching           # Deterministic routing
```

Opens ADK's built-in web UI at http://localhost:8000.

### Option 2: `adk run` (CLI)

```bash
cd examples
adk run simple_agent              # Interactive CLI chat
```

### Option 3: Visual Cookbook Runner (custom frontend)

The visual runner is a custom web frontend with live A2UI surface rendering.

```bash
# Generate agent folders (one-time)
just agents                       # or: uv run python scripts/cookbook_to_agents.py --force

# Configure visual runner credentials
cp visual/.env.example visual/.env
# Edit visual/.env with your API key

# Launch
just visual                       # or: uv run uvicorn visual.server:app --port 8099 --reload
```

Opens at **http://localhost:8099** with:
- **Left sidebar** — all cookbooks grouped by difficulty
- **Center panel** — interactive chat with any agent
- **Right panel** — live A2UI surface rendering + JSON inspector

### Option 4: A2UI Preview (no API key)

Browse A2UI component surfaces without any LLM calls:

```bash
just a2ui-preview
```

Opens a static gallery of all A2UI surfaces from cookbooks 70-74.

### Option 5: pytest (automated)

```bash
# Run all cookbook examples as tests (no API key — tests compilation only)
uv run pytest examples/cookbook/ -v

# Run a specific cookbook
uv run pytest examples/cookbook/01_simple_agent.py -v
```

## Generating Agent Folders

Agent folders are auto-generated from cookbook files:

```bash
just agents                       # Generate/regenerate all agent folders
```

This converts each `examples/cookbook/XX_name.py` into `examples/name/agent.py` — compatible with `adk web`, `adk run`, and `adk deploy`.

## Useful Commands

| Command | Description |
|---------|-------------|
| `just agents` | Generate agent folders from cookbooks |
| `just visual` | Launch visual cookbook runner (port 8099) |
| `just a2ui-preview` | Static A2UI gallery (no API key) |
| `just test` | Run all tests |
| `adk web <name>` | Run an agent in ADK's web UI |
| `adk run <name>` | Run an agent in CLI mode |

## Troubleshooting

**"No module named 'adk_fluent'"** — Install the package: `pip install -e .` from the repo root.

**"GOOGLE_API_KEY not set"** — Copy `.env.example` to `.env` and add your key.

**"just: command not found"** — Install just: `brew install just` (macOS) or `cargo install just` (Linux). Alternatively, run the underlying commands directly (shown in parentheses above).

**Agent folder missing** — Run `just agents` to regenerate all agent folders from cookbooks.

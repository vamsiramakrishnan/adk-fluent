# Distributed agents

Agents that cross process or host boundaries — other teams' agents
reached over the network, and agents that render UI instead of text.

```{mermaid}
flowchart LR
    local[Local agent] -->|.a2a_client or<br/>RemoteAgent| remote[Remote agent<br/>different host]
    local -->|.ui spec or<br/>UI.auto| ui[User interface<br/>browser, app]

    classDef local fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    classDef remote fill:#fff3e0,stroke:#e65100,color:#bf360c
    classDef ui fill:#f3e5f5,stroke:#6a1b9a,color:#4a148c
    class local local
    class remote remote
    class ui ui
```

## Chapters

| Chapter | Read when |
|---|---|
| [A2A (remote agents)](a2a.md) | You need to call another team's agent over HTTP (`RemoteAgent`), or publish yours (`A2AServer`). |
| [A2UI (agent-to-UI)](a2ui.md) | The agent's "output" is a form, dashboard, or interactive surface — not prose. |

:::{tip} A2A vs normal tool calls
If the remote thing is an ADK agent that speaks the A2A protocol,
use `RemoteAgent` — you get session continuity, streaming, and
typed error handling. If it's a generic HTTP API, wrap it as a
regular tool with `T.fn()`. Don't reach for A2A for everything
remote.
:::

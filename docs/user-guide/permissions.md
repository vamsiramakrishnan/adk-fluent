# Permissions

The `adk_fluent._permissions` package is adk-fluent's decision-based permission
foundation. It mirrors [Claude Agent SDK's `canUseTool`
surface](https://docs.anthropic.com/en/docs/claude-code/sdk) and the five
permission modes — `default`, `accept_edits`, `plan`, `bypass`, `dont_ask` —
while staying native to Google ADK's plugin architecture.

A permission policy answers one question for every tool call:

> *Should this tool run, and with what arguments?*

The answer is a structured [`PermissionDecision`](#permissiondecision) — not a
string — and the policy itself is a frozen dataclass you can compose, merge,
and hand around safely.

## Quick start

```python
from adk_fluent import Agent, H, PermissionMode

agent = (
    Agent("coder", "gemini-2.5-flash")
    .instruct("You are a senior engineer.")
    .harness(
        permissions=H.permissions(
            mode=PermissionMode.ACCEPT_EDITS,
            allow=["read_file", "grep"],
            deny=["bash"],
            ask=["write_file"],
        ),
    )
)
```

Everything the harness needs — policy, sandbox, usage, memory — is declared
up front. The policy object is just data, so it travels across agents,
subagents, and plugins without surprises.

## The four pieces

| Piece | What it is | Where it lives |
| --- | --- | --- |
| `PermissionPolicy` | Declarative rules + mode | `adk_fluent._permissions._policy` |
| `PermissionDecision` | Frozen dataclass describing the answer | `adk_fluent._permissions._decision` |
| `ApprovalMemory` | Session-scoped record of interactive approvals | `adk_fluent._permissions._memory` |
| `PermissionPlugin` | ADK `BasePlugin` that enforces a policy at runtime | `adk_fluent._permissions._plugin` |

All four are re-exported from the top-level `adk_fluent` package and from
the `H` harness namespace, so `from adk_fluent import PermissionPolicy` and
`H.permissions(...)` both work.

## `PermissionDecision`

Every `PermissionPolicy.check()` call returns a `PermissionDecision`:

```python
from adk_fluent import PermissionDecision

PermissionDecision.allow()
PermissionDecision.allow(updated_input={"path": "/safe/dir"})
PermissionDecision.deny("bash is disabled in this environment")
PermissionDecision.ask("Allow tool 'edit_file'?")
```

Four fields, three constructors, and a handful of predicates:

```python
decision.is_allow   # True if allowed
decision.is_deny    # True if denied
decision.is_ask     # True if deferred to a handler
decision.is_terminal  # True if allow or deny (i.e. no handler needed)

decision.behavior     # "allow" | "deny" | "ask"
decision.reason       # populated on deny
decision.prompt       # populated on ask
decision.updated_input  # populated on allow when rewriting args
```

Decisions are **frozen dataclasses**, which means they are safe to cache,
compare, and pass between threads. The `updated_input` field is how policies
rewrite arguments before a tool runs — think "sanitise the path" or "strip
a secret". The plugin applies it by mutating `tool_args` in place, the same
trick [`HookDecision.modify`](hooks.md#modify) uses.

## Permission modes

Five modes match Claude Agent SDK 1:1:

| Mode | Posture |
| --- | --- |
| `default` | Ask for everything not explicitly allowed |
| `accept_edits` | Auto-allow mutating file ops; ask for the rest |
| `plan` | Deny every mutating tool (read-only exploration) |
| `bypass` | Allow everything except explicit denies |
| `dont_ask` | Deny everything not explicitly allowed (non-interactive) |

`PermissionMode` provides the constants:

```python
from adk_fluent import PermissionMode

PermissionMode.DEFAULT       # "default"
PermissionMode.ACCEPT_EDITS  # "accept_edits"
PermissionMode.PLAN          # "plan"
PermissionMode.BYPASS        # "bypass"
PermissionMode.DONT_ASK      # "dont_ask"
```

The `H` namespace exposes one-liner factories for each mode:

```python
H.permissions_plan()         # plan mode, read-only by default
H.permissions_bypass()       # bypass mode
H.permissions_accept_edits() # accept_edits mode
H.permissions_dont_ask(allow=["read_file"])  # non-interactive
```

These return a `PermissionPolicy` — they are shortcuts for
`PermissionPolicy(mode=...)` with sensible defaults.

## Precedence rules

The policy's `check(tool_name, tool_input)` method walks a fixed precedence
chain. Learn it once and the rest of the system becomes predictable.

```
1. tool_name in deny                 → deny
2. matches any deny pattern           → deny
3. mode == BYPASS                     → allow
4. mode == PLAN and tool is mutating  → deny
5. tool_name in allow                 → allow
6. matches any allow pattern          → allow
7. mode == ACCEPT_EDITS and mutating  → allow
8. mode == DONT_ASK                   → deny
9. tool_name in ask                   → ask
10. matches any ask pattern           → ask
11. fallback based on mode            → ask | deny
```

Three invariants fall out of this chain:

1. **Deny always wins.** You can never "allow through" an explicit deny.
2. **Plan mode denies mutating tools even if they are on the allow list.**
   The point of plan mode is to prove the agent can describe its plan without
   side effects. An allow list cannot override that.
3. **Arguments are never inspected by the policy.** Content-level filtering
   (path globs, command substrings) belongs in [hooks](hooks.md), not the
   policy object. Keeping the policy argument-free is what makes it
   composable.

## Composing policies

Policies compose via `merge` and are otherwise immutable:

```python
base    = H.auto_allow("read_file", "grep", "list_dir")
strict  = H.deny_patterns("*secret*", "*.env")
policy  = base.merge(strict).with_mode(PermissionMode.DEFAULT)
```

Merge semantics:

- `deny` unions — any side's deny wins.
- `allow` unions, minus anything in the combined deny.
- `ask` unions, minus anything in the combined allow or deny.
- Pattern tuples concatenate.
- The non-default `mode` wins if the two sides disagree.
- `mutating_tools` unions.

Because every policy is frozen, you can keep a library of reusable fragments
(`STRICT_NETWORK`, `READ_ONLY_FS`, `DESTRUCTIVE_COMMANDS`) and merge them on
demand without worrying about shared mutable state.

## Patterns: glob vs regex

Policies accept glob (default) or regex patterns:

```python
PermissionPolicy(
    allow_patterns=("read_*", "list_*"),
    deny_patterns=("*secret*",),
    pattern_mode="glob",  # or "regex"
)
```

Regex patterns use `re.fullmatch` — you do not need explicit anchors, but
partial matches are rejected. Glob patterns use `fnmatch.fnmatchcase`, so
matching is case-sensitive and OS-independent.

## Interactive approval

Policies that evaluate to `ask` defer to a user-provided handler. The
`PermissionPlugin` runs the handler exactly once per unique `(tool, args)`
pair and persists the answer in an `ApprovalMemory` so repeat calls are
resolved without re-prompting.

```python
from adk_fluent import H

async def approve(tool_name, tool_args, decision):
    print(f"Agent wants to run {tool_name}({tool_args}).")
    print(f"  reason: {decision.prompt}")
    return input("Allow? [y/N] ").lower().startswith("y")

plugin = H.permission_plugin(
    H.ask_before("bash", "edit_file"),
    handler=approve,
    memory=H.approval_memory(),
)
```

Both sync and async handlers are supported — the plugin awaits awaitables
automatically. Exceptions raised by a handler become `deny` decisions (same
defensive stance as the hooks layer).

## Installing the plugin at the `App` layer

The canonical runtime for permissions is a session-scoped ADK plugin:

```python
from adk_fluent.backends.adk import compile_app

app = compile_app(agent, plugins=[plugin])
```

Because ADK plugins are session-scoped and subagent-inherited, a single
plugin covers *every* tool call — including calls made by child agents,
manifold capabilities, and dynamically spawned subagents. You do not need
to walk the agent tree or re-install the plugin per branch.

## Agent-level callback adapter

For surfaces that still expose permissions as an agent-level callback — most
notably `.harness()` on the fluent builder — a synchronous adapter produces
an ADK-compatible `before_tool_callback`:

```python
from adk_fluent._permissions._callback import make_permission_callback

cb = make_permission_callback(
    policy,
    handler=approve_sync,       # must be sync in this path
    memory=H.approval_memory(),
)
```

The adapter enforces the same precedence rules as `PermissionPlugin` but runs
in the sync ADK callback path. Use it when you cannot reach the `App` layer;
otherwise prefer the plugin.

## `ApprovalMemory`

`ApprovalMemory` is a tiny in-memory store keyed by
`(tool_name, sha256(json.dumps(args)))`:

```python
mem = H.approval_memory()
mem.remember_specific("bash", {"cmd": "ls"}, True)     # args-specific
mem.remember_tool("read_file", True)                    # tool-wide
mem.recall("bash", {"cmd": "ls"})                       # → True
mem.recall("bash", {"cmd": "rm -rf /"})                 # → None
mem.clear()
```

`None` means "not remembered"; `True`/`False` are the recorded verdicts.
Passing a memory object into the plugin is the difference between "ask me
once per session" and "ask me every time".

## Cookbook

### Read-only exploration during planning

```python
agent.harness(
    permissions=H.permissions_plan(allow=["read_file", "grep", "list_dir"]),
)
```

### Trusted CI runner (non-interactive)

```python
agent.harness(
    permissions=H.permissions_dont_ask(
        allow=["read_file", "write_file", "bash"],
    ),
)
```

### Coding agent with approval prompts for shell

```python
agent.harness(
    permissions=(
        H.permissions_accept_edits(ask=["bash", "streaming_bash"])
        .merge(H.deny("rm", "sudo", "curl"))
    ),
    approval_handler=approve_sync,
)
```

### Sanitising arguments before a tool runs

Subclass `PermissionPolicy` and return `allow(updated_input=...)`:

```python
from adk_fluent import PermissionPolicy, PermissionDecision

class ClampPathsPolicy(PermissionPolicy):
    def check(self, tool_name, tool_input=None):
        base = super().check(tool_name, tool_input)
        if base.is_allow and tool_name == "read_file":
            path = (tool_input or {}).get("path", "")
            if path.startswith("/etc/"):
                return PermissionDecision.deny("refusing to read /etc/*")
            if ".." in path:
                return PermissionDecision.allow(
                    updated_input={"path": path.replace("..", "")}
                )
        return base
```

The plugin mutates the tool's argument dict in place, so by the time the
tool runs, it sees the rewritten input.

## Relationship to hooks

Permissions and [hooks](hooks.md) are orthogonal plugins:

- **Permissions** answer "may this tool run?".
- **Hooks** transform the tool call — inject nudges, redact secrets, log,
  replace arguments.

The permission plugin sits *before* the hook plugin in the ADK chain, so a
denied tool never fires its hooks. Both plugins are session-scoped, so
installing them on the root `App` covers every subagent automatically.

## API reference

### `PermissionPolicy`

```python
PermissionPolicy(
    mode: str = PermissionMode.DEFAULT,
    allow: frozenset[str] = frozenset(),
    deny: frozenset[str] = frozenset(),
    ask: frozenset[str] = frozenset(),
    allow_patterns: tuple[str, ...] = (),
    deny_patterns: tuple[str, ...] = (),
    ask_patterns: tuple[str, ...] = (),
    pattern_mode: str = "glob",  # or "regex"
    mutating_tools: frozenset[str] = DEFAULT_MUTATING_TOOLS,
)
```

Methods:

- `.check(tool_name, tool_input=None) → PermissionDecision`
- `.merge(other) → PermissionPolicy`
- `.with_mode(mode) → PermissionPolicy`
- `.is_mutating(tool_name) → bool`

### `PermissionDecision`

Constructors: `.allow(updated_input=None)`, `.deny(reason)`, `.ask(prompt)`.

Predicates: `.is_allow`, `.is_deny`, `.is_ask`, `.is_terminal`.

### `PermissionPlugin`

```python
PermissionPlugin(
    policy: PermissionPolicy,
    *,
    handler: PermissionHandler | None = None,
    memory: ApprovalMemory | None = None,
    name: str = "adkf_permission_plugin",
)
```

The plugin exposes `.policy` and `.memory` properties and implements the
ADK `before_tool_callback` hook.

### `ApprovalMemory`

- `.remember_specific(tool_name, args, granted)`
- `.remember_tool(tool_name, granted)`
- `.recall(tool_name, args) → bool | None`
- `.clear()`

### `H` namespace factories

- `H.permissions(mode=..., allow=..., deny=..., ask=..., ...)`
- `H.permissions_plan(allow=...)`
- `H.permissions_bypass()`
- `H.permissions_accept_edits(ask=...)`
- `H.permissions_dont_ask(allow=...)`
- `H.ask_before(*tools)` · `H.auto_allow(*tools)` · `H.deny(*tools)`
- `H.allow_patterns(*patterns, mode="glob")` · `H.deny_patterns(*patterns)`
- `H.permission_plugin(policy, handler=None, memory=None)`
- `H.permission_decision()` — returns the `PermissionDecision` class
- `H.approval_memory()` — fresh `ApprovalMemory` instance

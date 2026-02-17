# ADK Samples — Fluent API Ports

These examples port complex multi-agent samples from Google's
[adk-samples](https://github.com/google/adk-samples/tree/main/python/agents)
repository to the adk-fluent API. Each page shows native ADK code alongside
the fluent equivalent, highlighting structural improvements.

| Sample | Pattern | Key Fluent Features |
| ------ | ------- | ------------------- |
| [LLM Auditor](llm-auditor.md) | Sequential pipeline + callbacks | `>>` operator, `.after_model()` |
| [Financial Advisor](financial-advisor.md) | Tool-based delegation + state passing | `.delegate()`, `.outputs()` |
| [Short Movie](short-movie.md) | Director with 4 sub-agents + generative tools | `.sub_agents()`, `.outputs()`, custom tools |
| [Deep Search](deep-search.md) | Loop with evaluation + typed output + custom agent | `Loop`, `.output_schema()`, nested `Pipeline` |
| [Brand Search](brand-search.md) | Router with nested sub-agents + web tools | `.sub_agents()`, nested agent hierarchies |
| [Travel Concierge](travel-concierge.md) | 6-group orchestrator + callbacks + state | `.delegate()`, massive boilerplate reduction |

## Aggregate Metrics

Across all 6 ported samples:

| Metric | Native ADK | Fluent API | Reduction |
| ------ | ---------- | ---------- | --------- |
| Agent definition files | 25 | 6 | 76% |
| Total files | 70+ | 18 | 74% |
| Directories | 35+ | 6 | 83% |
| `AgentTool(agent=...)` calls | 20+ | 0 | 100% |

```{toctree}
:maxdepth: 1

llm-auditor
financial-advisor
short-movie
deep-search
brand-search
travel-concierge
```

---
name: research_pipeline
description: >
  Multi-step research pipeline with fact-checking and synthesis.
  Use when the user needs comprehensive research with citations.
version: "1.0.0"
tags: [research, synthesis, citations]

agents:
  researcher:
    model: gemini-2.5-flash
    instruct: |
      Research {topic} thoroughly using available tools.
      Find primary sources and extract key findings.
      Be factual and cite your sources.
    tools: [web_search]
    writes: findings

  fact_checker:
    model: gemini-2.5-flash
    instruct: |
      Review the research findings below and verify the claims.
      Flag any unsupported assertions or factual errors.

      Findings to verify:
      {findings}
    reads: [findings]
    writes: verified_findings

  synthesizer:
    model: gemini-2.5-pro
    instruct: |
      Synthesize the verified findings into a coherent, well-structured
      report. Include citations for all claims. Write for a technical
      audience.

      Verified findings:
      {verified_findings}
    reads: [verified_findings]
    writes: report

topology: researcher >> fact_checker >> synthesizer

input:
  topic: str
output:
  report: str

eval:
  - prompt: "Research recent advances in quantum error correction"
    rubrics: ["Contains citations", "Technically accurate", "Well-structured"]
  - prompt: "Research the impact of LLMs on software engineering"
    rubrics: ["Balanced perspective", "Contains data points"]
---

# Research Pipeline Skill

A multi-step research pipeline that ensures quality through fact-checking.

## When to use

- User needs comprehensive research on a topic
- Citations and fact-checking are important
- Multiple perspectives needed

## How it works

1. **Researcher** gathers information using web search
2. **Fact Checker** verifies claims and flags issues
3. **Synthesizer** produces a polished report with citations

## Customization

Override the model for all agents:
```python
Skill("skills/research_pipeline/").model("gemini-2.5-pro")
```

Inject a custom search tool:
```python
Skill("skills/research_pipeline/").inject(web_search=my_search_fn)
```

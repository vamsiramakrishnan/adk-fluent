---
name: code_reviewer
description: >
  Code review skill that checks for bugs, style issues, and security
  vulnerabilities. Returns structured review feedback.
version: "1.0.0"
tags: [code, review, security]

agents:
  analyzer:
    model: gemini-2.5-flash
    instruct: |
      Analyze the code for potential bugs, logic errors, and edge cases.
      List each issue with severity (critical/warning/info) and line reference.
    writes: bug_report

  style_checker:
    model: gemini-2.5-flash
    instruct: |
      Review the code for style consistency, naming conventions, and
      readability. Suggest improvements.
    writes: style_report

  security_auditor:
    model: gemini-2.5-flash
    instruct: |
      Check the code for security vulnerabilities: injection, XSS,
      authentication issues, secrets exposure. Flag any OWASP top 10 risks.
    writes: security_report

  summarizer:
    model: gemini-2.5-pro
    instruct: |
      Combine the three review reports into a unified code review.
      Prioritize by severity. Format as markdown with sections.

      Bug report: {bug_report}
      Style report: {style_report}
      Security report: {security_report}
    reads: [bug_report, style_report, security_report]

topology: (analyzer | style_checker | security_auditor) >> summarizer

input:
  code: str
output:
  review: str
---

# Code Reviewer Skill

Parallel code review with bug detection, style checking, and security audit.

## Topology

```
analyzer ──┐
style    ──┤──>> summarizer
security ──┘
```

Three reviewers run in parallel (FanOut), then results are merged by a
synthesizer agent.

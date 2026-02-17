# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.4.x   | Yes                |
| < 0.4   | No                 |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Email the maintainers or use [GitHub's private vulnerability reporting](https://github.com/vamsiramakrishnan/adk-fluent/security/advisories/new)
3. Include a description of the vulnerability and steps to reproduce

We will acknowledge receipt within 48 hours and provide a fix timeline within 7 days.

## Scope

adk-fluent is a build-time library that generates ADK agent configurations. It does not handle user data, authentication, or network requests directly. Security concerns are most likely to involve:

- Code injection through the codegen pipeline
- Unsafe deserialization in `from_dict()` / `from_yaml()`
- Dependencies with known vulnerabilities

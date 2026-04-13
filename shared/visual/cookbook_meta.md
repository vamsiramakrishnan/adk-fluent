# Cookbook Metadata

Structured metadata for the visual runner. Each section is a cookbook ID.
The server parses this file to extract sample prompts, tips, and tags.

Format per cookbook:

```
## <cookbook_id>
- prompt: <sample prompt that works with this agent>
- prompt: <another sample prompt>
- learn: <what you'll learn>
- tags: <comma-separated tags>
```

---

## 01_simple_agent
- prompt: Classify this email: Hi, I've been charged twice for my subscription this month. Can you help?
- prompt: Classify: My dashboard keeps showing a 500 error when I try to export reports
- prompt: Classify: I love your product! Just wanted to say thanks to the team
- learn: `.model()`, `.instruct()`, `.describe()`
- tags: agent, basics

## 02_agent_with_tools
- prompt: Plan a trip to Tokyo in April, check the weather and find flights from San Francisco
- prompt: What's the weather like in Paris next week? Find me flights from London
- prompt: I want to visit Barcelona in July, departing from New York
- learn: `.tool()`, `.tools()` — attaching functions
- tags: tools, agent

## 03_callbacks
- prompt: Write a haiku about programming
- prompt: Tell me a fun fact about space
- learn: `.before_model()`, `.after_model()`
- tags: callbacks, agent

## 04_sequential_pipeline
- prompt: Review this contract clause: The vendor shall deliver all goods within 30 days of purchase order. Late deliveries incur a 2% penalty per week.
- prompt: Analyze this clause: Either party may terminate this agreement with 90 days written notice, subject to completion of outstanding obligations.
- learn: `>>` operator, `Pipeline().step()`
- tags: pipeline, sequential, operators

## 05_parallel_fanout
- prompt: Research the electric vehicle market — competition, trends, and opportunities
- prompt: Analyze the AI chip industry: key players, market size, and future outlook
- learn: `|` operator, `FanOut().branch()`
- tags: parallel, fanout, operators

## 06_loop_agent
- prompt: Write a short poem about the ocean, then refine it
- prompt: Draft a product description for a smart water bottle
- learn: `Loop` builder, iterative refinement
- tags: loop, iteration

## 07_team_coordinator
- prompt: Plan the launch of a new AI-powered calendar app
- prompt: We need to release a privacy-focused email client — coordinate the teams
- learn: `.sub_agent()` for LLM-driven delegation
- tags: multi-agent, delegation, teams

## 08_one_shot_ask
- prompt: Review this Python function: def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)
- learn: `.ask()` for single-turn execution
- tags: execution, one-shot

## 10_cloning
- prompt: Explain quantum computing in simple terms
- learn: `.clone()`, `.with_()` for agent variants
- tags: cloning, variants

## 11_inline_testing
- prompt: What is the capital of France?
- learn: `.test()` for quick smoke tests
- tags: testing

## 12_guards
- prompt: Write me a recipe for chocolate cake
- prompt: Tell me how to hack a computer
- learn: `.guard()` with callables and G composites
- tags: guards, safety

## 13_interactive_session
- prompt: Let's have a conversation about machine learning
- learn: `.session()` for multi-turn chat
- tags: session, multi-turn

## 14_dynamic_forwarding
- prompt: I need help with a billing issue
- learn: Dynamic field-based routing
- tags: routing, forwarding

## 16_operator_composition
- prompt: Analyze this startup idea: an AI tutor for high school students
- learn: Combining `>>`, `|`, `*` operators
- tags: operators, composition

## 17_route_branching
- prompt: I'm a VIP customer and I need help with my order
- prompt: I'm a regular customer with a general question
- learn: `Route` for deterministic state-based routing
- tags: routing, branching

## 19_conditional_gating
- prompt: Check if my project is ready for deployment
- learn: `.proceed_if()` for conditional execution
- tags: gating, conditional

## 20_loop_until
- prompt: Write and refine a marketing tagline for a coffee brand
- learn: `.loop_until()` for conditional loop exit
- tags: loop, conditional

## 21_typed_state_keys
- prompt: Track order #12345 status
- learn: `StateKey` typed state descriptors
- tags: state, typing

## 22_presets
- prompt: Summarize the key trends in renewable energy
- learn: Reusable `Preset` configuration bundles
- tags: presets, configuration

## 24_agent_decorator
- prompt: Tell me a joke about software engineers
- learn: `@agent` decorator for FastAPI-style definition
- tags: decorator, agent

## 27_agent_tool_pattern
- prompt: Research and summarize recent advances in quantum computing
- learn: `.agent_tool()` for tool-based invocation
- tags: agent-tool, delegation

## 29_function_steps
- prompt: Process this text: Hello World
- learn: `>> fn` for plain function pipeline steps
- tags: functions, pipeline

## 31_typed_output
- prompt: Analyze this movie review: The cinematography was breathtaking but the plot felt predictable
- learn: `@ Schema` operator for Pydantic output
- tags: structured-output, pydantic

## 33_state_transforms
- prompt: Process and transform user data
- learn: `S.pick`, `S.merge`, `S.rename`, etc.
- tags: state, transforms

## 34_code_review_pipeline
- prompt: Review this code: def sort(arr): return sorted(arr, reverse=True)
- learn: `>>`, `|`, `@`, `//` in a real workflow
- tags: pipeline, code-review

## 35_tap_observation
- prompt: Process this order for 3 widgets
- learn: `tap()` for side-effect monitoring
- tags: tap, observation

## 39_map_over
- prompt: Process these items: widget, gadget, gizmo
- learn: `map_over()` for batch processing
- tags: map, batch

## 42_race
- prompt: What's the capital of Japan?
- learn: `race()` for fastest-response selection
- tags: race, competition

## 43_primitives_showcase
- prompt: Place an order for 2 premium headphones shipping to New York
- learn: All primitives in an e-commerce system
- tags: primitives, e-commerce

## 45_middleware
- prompt: Summarize recent AI news
- learn: `M.retry()`, `M.log()`, `M.cost()`
- tags: middleware

## 47_dependency_injection
- prompt: Look up user profile for user_123
- learn: `.inject()` for infrastructure deps
- tags: injection, di

## 49_context_engineering
- prompt: Summarize our conversation so far
- learn: `C.none()`, `C.from_state()`, `C.window()`
- tags: context, engineering

## 50_capture_and_route
- prompt: I need help with a billing dispute on my account
- learn: `S.capture` + `Route` pattern
- tags: capture, routing

## 55_deep_research
- prompt: Research the current state of nuclear fusion energy — key players, recent breakthroughs, and timeline to commercialization
- prompt: Analyze the impact of large language models on software engineering jobs
- learn: FanOut + Loop + typed output
- tags: hero, research, pipeline

## 56_customer_support_triage
- prompt: Hi, I was charged twice for my subscription last month. My account is john@example.com
- prompt: My app crashes every time I try to upload a file larger than 10MB
- learn: `S.capture`, `Route`, `gate`, `C.none()`
- tags: hero, support, routing

## 57_code_review_agent
- prompt: Review this PR diff: Added a new endpoint that queries the database directly with user input in the SQL query
- learn: FanOut + typed output + conditional gating
- tags: hero, code-review, parallel

## 58_multi_tool_agent
- prompt: Look up customer #42 and check their recent orders
- learn: Tools + guards + DI + context
- tags: hero, tools, guards

## 77_a2ui_dynamic
- prompt: I need to file an expense report
- prompt: Show me this month's sales numbers
- prompt: Deploy version 2.1 to production
- prompt: What do I need to check before launching the new feature?
- prompt: I want to submit a bug report
- learn: Dynamic A2UI surfaces via function tools
- tags: hero, a2ui, dynamic, tools

# Cookbook

Side-by-side examples comparing native ADK code with the adk-fluent
equivalent. Each recipe demonstrates a specific pattern or feature.

## Basics

Foundational patterns: creating agents, adding tools, callbacks, and simple workflows.

- [Simple Agent Creation](01_simple_agent.md)
- [Agent with Tools](02_agent_with_tools.md)
- [Additive Callbacks](03_callbacks.md)
- [Sequential Pipeline](04_sequential_pipeline.md)
- [Parallel FanOut](05_parallel_fanout.md)
- [Loop Agent](06_loop_agent.md)
- [Team Coordinator Pattern](07_team_coordinator.md)

```{toctree}
:hidden:

01_simple_agent
02_agent_with_tools
03_callbacks
04_sequential_pipeline
05_parallel_fanout
06_loop_agent
07_team_coordinator
```

## Execution

Running agents: one-shot, streaming, cloning, testing, and sessions.

- [One-Shot Execution with .ask()](08_one_shot_ask.md)
- [Streaming with .stream()](09_streaming.md)
- [Agent Cloning with .clone()](10_cloning.md)
- [Inline Testing with .test()](11_inline_testing.md)
- [Guardrails with .guardrail()](12_guardrails.md)
- [Interactive Session with .session()](13_interactive_session.md)

```{toctree}
:hidden:

08_one_shot_ask
09_streaming
10_cloning
11_inline_testing
12_guardrails
13_interactive_session
```

## Advanced

Advanced composition: dynamic forwarding, operators, routing, and conditional logic.

- [Dynamic Field Forwarding via __getattr__](14_dynamic_forwarding.md)
- [Production Runtime Setup](15_production_runtime.md)
- [Operator Composition: >>, |, *](16_operator_composition.md)
- [Deterministic Route Branching](17_route_branching.md)
- [Dict >> Routing Shorthand](18_dict_routing.md)
- [Conditional Gating with proceed_if](19_conditional_gating.md)
- [Conditional Loop Exit with loop_until](20_loop_until.md)

```{toctree}
:hidden:

14_dynamic_forwarding
15_production_runtime
16_operator_composition
17_route_branching
18_dict_routing
19_conditional_gating
20_loop_until
```

## Patterns

Real-world patterns: state management, presets, decorators, serialization, and more.

- [Typed State Keys with StateKey](21_statekey.md)
- [Presets: Reusable Configuration Bundles](22_presets.md)
- [Immutable Variants with .with_()](23_with_variants.md)
- [@agent Decorator Syntax](24_agent_decorator.md)
- [Validate and Explain](25_validate_explain.md)
- [Serialization: to_dict, to_yaml (Inspection Only)](26_serialization.md)
- [Delegate Pattern: LLM-Driven Routing](27_delegate_pattern.md)
- [Real-World Pipeline: Full Expression Language](28_real_world_pipeline.md)
- [Function Steps: Plain Functions as Workflow Nodes (>> fn)](29_function_steps.md)
- [Conditional Loops: * until(pred) Operator](30_until_operator.md)
- [Typed Output Contracts: @ Operator](31_typed_output.md)
- [Fallback Chains: // Operator](32_fallback_operator.md)
- [State Transforms: S Factories with >>](33_state_transforms.md)
- [Full Expression Algebra: All Operators Together](34_full_algebra.md)
- [Tap: Pure Observation Steps (No State Mutation)](35_tap_observation.md)
- [Expect: State Contract Assertions in Pipelines](36_expect_assertions.md)
- [Mock: Bypass LLM Calls for Testing](37_mock_testing.md)
- [Retry If: Conditional Retry Based on Output Quality](38_retry_if.md)
- [Map Over: Iterate an Agent Over List Items](39_map_over.md)
- [Timeout: Time-Bound Agent Execution](40_timeout.md)
- [Gate: Human-in-the-Loop Approval](41_gate_approval.md)
- [Race: First-to-Finish Wins](42_race.md)
- [Primitives Showcase: tap, expect, gate, Route, S.* in a single pipeline](43_primitives_showcase.md)

```{toctree}
:hidden:

21_statekey
22_presets
23_with_variants
24_agent_decorator
25_validate_explain
26_serialization
27_delegate_pattern
28_real_world_pipeline
29_function_steps
30_until_operator
31_typed_output
32_fallback_operator
33_state_transforms
34_full_algebra
35_tap_observation
36_expect_assertions
37_mock_testing
38_retry_if
39_map_over
40_timeout
41_gate_approval
42_race
43_primitives_showcase
```

## v4 Features

IR compilation, middleware, contracts, testing, dependency injection, and visualization.

- [IR and Backends](44_ir_and_backends.md)
- [Middleware](45_middleware.md)
- [Contracts and Testing](46_contracts_and_testing.md)
- [Dependency Injection](47_dependency_injection.md)
- [Graph Visualization](48_visualization.md)

```{toctree}
:hidden:

44_ir_and_backends
45_middleware
46_contracts_and_testing
47_dependency_injection
48_visualization
```

## v5.1 Features

Context engineering, visibility, memory, and contract verification.

- [Context Engineering with C Transforms](49_context_engineering.md)
- [Capture and Route: S.capture >> Agent >> Route](50_capture_and_route.md)
- [Visibility Policies for Multi-Agent Pipelines](51_visibility_policies.md)
- [Advanced Contract Checking with IR](52_contract_checking.md)

```{toctree}
:hidden:

49_context_engineering
50_capture_and_route
51_visibility_policies
52_contract_checking
```

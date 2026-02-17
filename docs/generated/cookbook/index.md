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
- [Serialization: to_dict, from_dict, to_yaml](26_serialization.md)
- [Delegate Pattern: LLM-Driven Routing](27_delegate_pattern.md)
- [Real-World Pipeline: Full Expression Language](28_real_world_pipeline.md)
- [Function Steps: Plain Functions as Workflow Nodes (>> fn)](29_function_steps.md)
- [Conditional Loops: * until(pred) Operator](30_until_operator.md)
- [Typed Output Contracts: @ Operator](31_typed_output.md)
- [Fallback Chains: // Operator](32_fallback_operator.md)
- [State Transforms: S Factories with >>](33_state_transforms.md)
- [Full Expression Algebra: All Operators Together](34_full_algebra.md)

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
```

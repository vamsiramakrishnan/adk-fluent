/**
 * adk-fluent-ts — Fluent builder API for Google's Agent Development Kit.
 *
 * Usage:
 *   import { Agent, Pipeline, FanOut, Loop } from "adk-fluent-ts";
 *   import { S, C, P, T, G, M, A, E, UI } from "adk-fluent-ts";
 *
 * Every `.build()` returns a real @google/adk object — fully compatible
 * with ADK's runtime, deployment, and tooling.
 */

// Core
export { BuilderBase, autoBuild } from "./core/builder-base.js";
export { until, UNSET } from "./core/types.js";
export type {
  State,
  StatePredicate,
  StateTransform,
  CallbackFn,
  ToolFn,
  UntilSpec,
} from "./core/types.js";

// Builders
export { Agent } from "./builders/agent.js";
export { Pipeline, FanOut, Loop, Fallback } from "./builders/workflow.js";

// Namespaces
export { S, STransform } from "./namespaces/state.js";
export { C, CTransform } from "./namespaces/context.js";
export { P, PTransform } from "./namespaces/prompt.js";
export { T, TComposite } from "./namespaces/tools.js";
export type { ToolSpec } from "./namespaces/tools.js";
export { G, GComposite, GuardViolation } from "./namespaces/guards.js";
export type { GuardSpec, PIIDetector, ContentJudge } from "./namespaces/guards.js";
export { M, MComposite } from "./namespaces/middleware.js";
export type { MiddlewareSpec } from "./namespaces/middleware.js";
export { A, AComposite } from "./namespaces/artifacts.js";
export type { ArtifactSpec } from "./namespaces/artifacts.js";
export {
  E,
  EComposite,
  ECase,
  EScenario,
  EvalReport,
  ComparisonReport,
  EvalSuite,
  ComparisonSuite,
} from "./namespaces/eval.js";
export type { ECriterion, EPersonaSpec } from "./namespaces/eval.js";
export { UI, UIComponent, UISurface } from "./namespaces/ui.js";
export type { UIBinding, UICheck } from "./namespaces/ui.js";

// Primitives — function-level building blocks (tap, expect, mapOver, ...)
export {
  Primitive,
  tap,
  expect,
  mapOver,
  gate,
  race,
  dispatch,
  join,
} from "./primitives/index.js";
export type { DispatchOptions } from "./primitives/index.js";

// Routing
export { Route } from "./routing/index.js";

// Composition patterns (review_loop, map_reduce, cascade, ...)
export {
  reviewLoop,
  mapReduce,
  cascade,
  fanOutMerge,
  chain,
  conditional,
  supervised,
} from "./patterns/index.js";
export type {
  ReviewLoopOptions,
  MapReduceOptions,
} from "./patterns/index.js";

// A2A — remote agent communication
export { RemoteAgent, A2AServer, AgentRegistry } from "./a2a/index.js";
export type { RemoteAgentOptions } from "./a2a/index.js";

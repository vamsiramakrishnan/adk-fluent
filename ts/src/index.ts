/**
 * adk-fluent-ts — Fluent builder API for Google's Agent Development Kit.
 *
 * Usage:
 *   import { Agent, Pipeline, FanOut, Loop } from "adk-fluent-ts";
 *   import { S, C, P, T, G, M } from "adk-fluent-ts";
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
export { G, GComposite, GuardViolation } from "./namespaces/guards.js";
export { M, MComposite } from "./namespaces/middleware.js";

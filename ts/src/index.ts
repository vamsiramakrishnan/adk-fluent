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

// H — Harness namespace (build-your-own coding agent)
export { H } from "./namespaces/harness/H.js";
export {
  PermissionPolicy,
  ApprovalMemory,
  PermissionMode,
  PermissionBehavior,
  PermissionDecision,
} from "./namespaces/harness/permissions.js";
export { SandboxPolicy } from "./namespaces/harness/sandbox.js";
export { ErrorStrategy } from "./namespaces/harness/error-strategy.js";
export { UsageTracker, CostTable, TurnUsage, AgentUsage } from "./namespaces/harness/usage.js";
export type { ModelRate } from "./namespaces/harness/usage.js";
export { ProjectMemory, MemoryHierarchy } from "./namespaces/harness/memory.js";
export { ArtifactStore } from "./namespaces/harness/artifacts.js";
export {
  EventDispatcher,
  EventBus,
  SessionTape,
  InMemoryBackend,
  JsonlBackend,
  NullBackend,
  ChainBackend,
} from "./namespaces/harness/events.js";
export type {
  HarnessEvent,
  HarnessEventKind,
  TextEvent,
  ToolEvent,
  ModelEvent,
  EventRecord,
  EventSubscriber,
  TapeBackend,
  StepLifecycleEvent,
  IterationLifecycleEvent,
  BranchLifecycleEvent,
  SubagentLifecycleEvent,
  AttemptFailedEvent,
  SignalChangedEvent,
} from "./namespaces/harness/events.js";
export {
  ContextCompressor,
  BudgetMonitor,
  BudgetPolicy,
  CancellationToken,
  AgentToken,
  TokenRegistry,
  ForkManager,
} from "./namespaces/harness/lifecycle.js";
// Reactor — reactive signals + priority-scheduled rule dispatch.
export { Signal, SignalPredicate, Reactor } from "./namespaces/reactor.js";
export type {
  SignalOptions,
  SignalSubscriber,
  PredicateFn,
  ReactorContext,
  ReactorHandler,
  ReactorOptions,
  ReactorRule,
  ReactorRuleOptions,
} from "./namespaces/reactor.js";
// Stream replay — resume from a cursor (Phase D).
export { streamFromCursor } from "./namespaces/harness/stream-replay.js";
export type { StreamFromCursorOptions } from "./namespaces/harness/stream-replay.js";
export type { BudgetThreshold, PreCompactHook } from "./namespaces/harness/lifecycle.js";
export {
  SessionStore,
  SessionSnapshot,
  SessionPlugin,
  Branch,
  ForkRegistry,
} from "./namespaces/harness/session-store.js";
export type {
  BranchOptions,
  ForkOptions,
  MergeOptions,
  MergeStrategy,
  ForkDiff,
  SessionSnapshotData,
  SessionStoreOptions,
  SessionPluginOptions,
} from "./namespaces/harness/session-store.js";
// Subagents — dynamic specialist spawner + task tool factory.
export {
  SubagentSpec,
  SubagentResult,
  SubagentRegistry,
  SubagentRunnerError,
  FakeSubagentRunner,
  makeTaskTool,
} from "./namespaces/harness/subagents.js";
export type {
  SubagentSpecOptions,
  SubagentResultOptions,
  SubagentRunner,
  FakeSubagentRunnerOptions,
  SubagentCall,
  TaskTool,
  MakeTaskToolOptions,
} from "./namespaces/harness/subagents.js";
// Pluggable filesystem backend for harness tools.
export {
  LocalBackend,
  MemoryBackend,
  SandboxedBackend,
  SandboxViolation,
} from "./namespaces/harness/fs.js";
export type { FsBackend, FsStat, FsEntry } from "./namespaces/harness/fs.js";
export {
  PlanModePolicy,
  planModeTools,
  planModeBeforeToolHook,
  MUTATING_TOOLS,
} from "./namespaces/harness/plan-mode.js";
export type { PlanState, PlanObserver } from "./namespaces/harness/plan-mode.js";
export {
  HookRegistry,
  HookEvent,
  HookDecision,
  HookMatcher,
  SystemMessageChannel,
  SYSTEM_MESSAGE_STATE_KEY,
  ALL_HOOK_EVENTS,
  CommandRegistry,
  ToolPolicy,
  TaskRegistry,
  TaskLedger,
} from "./namespaces/harness/registries.js";
export type {
  HookContext,
  HookAction,
  HookDecisionFields,
  HookMatcherOptions,
  HookCallable,
  HookEntry,
  HookOnOptions,
  HookShellOptions,
  HookSpec,
} from "./namespaces/harness/registries.js";
export { PlainRenderer, RichRenderer, JsonRenderer } from "./namespaces/harness/renderer.js";
export type { Renderer, RendererOptions } from "./namespaces/harness/renderer.js";
export { GitCheckpointer } from "./namespaces/harness/git.js";
export { HarnessRepl } from "./namespaces/harness/repl.js";
export { HarnessConfig } from "./namespaces/harness/config.js";
export { CodeExecutor } from "./namespaces/harness/code-executor.js";
export type {
  CodeLanguage,
  CodeExecutorOptions,
  CodeRunResult,
} from "./namespaces/harness/code-executor.js";
export { StreamingBash } from "./namespaces/harness/streaming.js";
export type { StreamingBashRunOptions } from "./namespaces/harness/streaming.js";
export {
  TodoStore,
  PlanMode,
  WorktreeManager,
  askUserTool,
} from "./namespaces/harness/agent-tools.js";
export type { TodoItem, TodoStatus, AskUserHandler } from "./namespaces/harness/agent-tools.js";
export { codingAgent } from "./namespaces/harness/coding-agent.js";
export type { CodingAgentOptions, CodingAgentBundle } from "./namespaces/harness/coding-agent.js";
export type { HarnessTool } from "./namespaces/harness/types.js";

// Primitives — function-level building blocks (tap, expect, mapOver, ...)
export { Primitive, tap, expect, mapOver, gate, race, dispatch, join } from "./primitives/index.js";
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
export type { ReviewLoopOptions, MapReduceOptions } from "./patterns/index.js";

// A2A — remote agent communication
export { RemoteAgent, A2AServer, AgentRegistry } from "./a2a/index.js";
export type { RemoteAgentOptions } from "./a2a/index.js";

// Visualization — render builder topologies as ascii / mermaid / markdown
export {
  visualize,
  normalize,
  renderAscii,
  renderMermaid,
  renderMarkdown,
} from "./visualize/index.js";
export type {
  VizNode,
  VisualizeFormat,
  VisualizeOptions,
  AsciiOptions,
  MermaidOptions,
  MarkdownOptions,
} from "./visualize/index.js";

/**
 * Workflow builders — Pipeline, FanOut, Loop, Fallback.
 *
 * These wrap @google/adk's SequentialAgent, ParallelAgent, and LoopAgent.
 */

import { BuilderBase, autoBuild, registerWorkflow } from "../core/builder-base.js";
import type { StatePredicate } from "../core/types.js";

/**
 * Sequential pipeline: runs agents in order.
 *
 * Usage:
 *   const pipeline = new Pipeline("flow")
 *     .step(new Agent("a").instruct("Step 1").writes("result"))
 *     .step(new Agent("b").instruct("Step 2 using {result}"))
 *     .build();
 */
export class Pipeline extends BuilderBase {
  constructor(name: string) {
    super(name);
  }

  /** Append an agent (or builder) as the next step. */
  step(agent: BuilderBase | unknown): this {
    return this._addToList("sub_agents", agent);
  }

  build(): unknown {
    const subAgents = (this._lists.get("sub_agents") ?? []).map((sa) =>
      autoBuild(sa as BuilderBase),
    );

    const config: Record<string, unknown> = {
      name: this._config.get("name"),
      subAgents,
    };

    // Copy description if set
    const desc = this._config.get("description");
    if (desc) config.description = desc;

    return { _type: "SequentialAgent", ...config };
  }
}

/**
 * Parallel fan-out: runs agents concurrently.
 *
 * Usage:
 *   const fanout = new FanOut("parallel")
 *     .branch(new Agent("web").instruct("Search web."))
 *     .branch(new Agent("papers").instruct("Search papers."))
 *     .build();
 */
export class FanOut extends BuilderBase {
  constructor(name: string) {
    super(name);
  }

  /** Add an agent (or builder) as a parallel branch. */
  branch(agent: BuilderBase | unknown): this {
    return this._addToList("sub_agents", agent);
  }

  build(): unknown {
    const subAgents = (this._lists.get("sub_agents") ?? []).map((sa) =>
      autoBuild(sa as BuilderBase),
    );

    const config: Record<string, unknown> = {
      name: this._config.get("name"),
      subAgents,
    };

    const desc = this._config.get("description");
    if (desc) config.description = desc;

    return { _type: "ParallelAgent", ...config };
  }
}

/**
 * Loop: repeats a workflow up to N times or until a predicate is satisfied.
 *
 * Usage:
 *   const loop = new Loop("refine")
 *     .step(new Agent("writer").instruct("Write."))
 *     .step(new Agent("critic").instruct("Critique."))
 *     .maxIterations(3)
 *     .build();
 */
export class Loop extends BuilderBase {
  constructor(name: string) {
    super(name);
    this._config.set("max_iterations", 10);
  }

  /** Append an agent (or builder) as a step in the loop body. */
  step(agent: BuilderBase | unknown): this {
    return this._addToList("sub_agents", agent);
  }

  /** Set maximum number of iterations. */
  maxIterations(n: number): this {
    return this._setConfig("max_iterations", n);
  }

  /** Set a termination predicate: stop looping when predicate returns true. */
  until(predicate: StatePredicate): this {
    return this._setConfig("_until_predicate", predicate);
  }

  build(): unknown {
    const subAgents = (this._lists.get("sub_agents") ?? []).map((sa) =>
      autoBuild(sa as BuilderBase),
    );

    const config: Record<string, unknown> = {
      name: this._config.get("name"),
      subAgents,
      maxIterations: this._config.get("max_iterations"),
    };

    const desc = this._config.get("description");
    if (desc) config.description = desc;

    return { _type: "LoopAgent", ...config };
  }
}

/**
 * Fallback chain: tries agents in order, first success wins.
 *
 * Usage:
 *   const fallback = new Fallback("resilient", [fastAgent, strongAgent]);
 */
export class Fallback extends BuilderBase {
  private _children: BuilderBase[];

  constructor(name: string, children: BuilderBase[] = []) {
    super(name);
    this._children = [...children];
  }

  /** Add a fallback alternative. */
  attempt(agent: BuilderBase): this {
    const clone = this._clone();
    clone._children = [...this._children, agent];
    return clone;
  }

  protected override _clone(): this {
    const clone = super._clone();
    (clone as Fallback)._children = [...this._children];
    return clone;
  }

  build(): unknown {
    const builtChildren = this._children.map((c) => autoBuild(c));
    return {
      _type: "Fallback",
      name: this._config.get("name"),
      children: builtChildren,
    };
  }
}

// Register workflow classes with builder-base to break circular import.
registerWorkflow("Pipeline", Pipeline);
registerWorkflow("FanOut", FanOut);
registerWorkflow("Loop", Loop);
registerWorkflow("Fallback", Fallback);

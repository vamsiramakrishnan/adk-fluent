/**
 * T — Tool composition namespace.
 *
 * Factory methods returning composable tool collections.
 *
 * Usage:
 *   agent.tools(T.fn(search).pipe(T.fn(email)))
 */

import type { ToolFn } from "../core/types.js";

/** A composable tool collection. */
export class TComposite {
  constructor(public readonly items: unknown[]) {}

  /** Chain: add another tool or composite. */
  pipe(other: TComposite): TComposite {
    return new TComposite([...this.items, ...other.items]);
  }

  /** Convert to a flat tool array for passing to builder. */
  toArray(): unknown[] {
    return [...this.items];
  }
}

/**
 * T namespace — tool composition factories.
 */
export class T {
  /** Wrap a callable as a FunctionTool. */
  static fn(callable: ToolFn, opts?: { name?: string; description?: string }): TComposite {
    return new TComposite([{ type: "function", fn: callable, ...opts }]);
  }

  /** Wrap an agent as an AgentTool. */
  static agent(
    agent: unknown,
    opts?: { name?: string; description?: string },
  ): TComposite {
    return new TComposite([{ type: "agent_tool", agent, ...opts }]);
  }

  /** Google Search built-in tool. */
  static googleSearch(opts?: Record<string, unknown>): TComposite {
    return new TComposite([{ type: "google_search", ...opts }]);
  }

  /** Mock tool for testing. */
  static mock(responses: Record<string, unknown>): TComposite {
    return new TComposite([{ type: "mock", responses }]);
  }

  /** Tool timeout wrapper. */
  static timeout(seconds: number): TComposite {
    return new TComposite([{ type: "timeout", seconds }]);
  }
}

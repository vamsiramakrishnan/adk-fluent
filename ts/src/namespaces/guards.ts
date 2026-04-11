/**
 * G — Guards (output validation) namespace.
 *
 * Guards validate/transform the LLM response (after_model).
 *
 * Usage:
 *   agent.guard(G.length({ max: 500 }))
 *   agent.guard(G.json())
 */

import type { CallbackFn } from "../core/types.js";

/** A composable guard descriptor. */
export class GComposite {
  constructor(public readonly guards: GuardSpec[]) {}

  /** Chain: add another guard. */
  pipe(other: GComposite): GComposite {
    return new GComposite([...this.guards, ...other.guards]);
  }
}

interface GuardSpec {
  name: string;
  check: CallbackFn;
}

/** Error thrown when a guard check fails. */
export class GuardViolation extends Error {
  constructor(
    public readonly guardName: string,
    public readonly phase: string,
    message: string,
  ) {
    super(message);
    this.name = "GuardViolation";
  }
}

/**
 * G namespace — guard factories.
 */
export class G {
  /** Custom guard function. */
  static guard(fn: CallbackFn): GComposite {
    return new GComposite([{ name: "custom", check: fn }]);
  }

  /** Validate that output is valid JSON. */
  static json(): GComposite {
    return new GComposite([
      {
        name: "json",
        check: (response: string) => {
          try {
            JSON.parse(response);
          } catch (e) {
            throw new GuardViolation("json", "post_model", `Output is not valid JSON: ${e}`);
          }
        },
      },
    ]);
  }

  /** Enforce max/min response length. */
  static length(opts: { min?: number; max?: number }): GComposite {
    const { min = 0, max = Infinity } = opts;
    return new GComposite([
      {
        name: "length",
        check: (response: string) => {
          const len = response.length;
          if (len < min) {
            throw new GuardViolation("length", "post_model", `Output too short (${len} < ${min})`);
          }
          if (len > max) {
            throw new GuardViolation("length", "post_model", `Output too long (${len} > ${max})`);
          }
        },
      },
    ]);
  }

  /** Validate output against a schema (e.g., Zod). */
  static schema(zodSchema: unknown): GComposite {
    return new GComposite([
      {
        name: "schema",
        check: (response: string) => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const result = (zodSchema as any).safeParse(JSON.parse(response));
          if (!result.success) {
            throw new GuardViolation("schema", "post_model", `Schema validation failed: ${result.error}`);
          }
        },
      },
    ]);
  }
}

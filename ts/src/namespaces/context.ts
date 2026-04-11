/**
 * C — Context engineering namespace.
 *
 * Controls what history and state data an agent sees.
 * Two categories:
 * - History-filtering: suppress/filter conversation history
 * - Data-injection: inject state without touching history
 *
 * Usage:
 *   agent.context(C.none())                      // suppress all history
 *   agent.context(C.window(5))                   // last 5 turn-pairs
 *   agent.context(C.none().inject(C.fromState("key")))  // no history, inject state
 */

/** A composable context transform descriptor. */
export class CTransform {
  constructor(
    public readonly name: string,
    public readonly config: Record<string, unknown>,
    public readonly suppressHistory: boolean = false,
    public readonly children: CTransform[] = [],
  ) {}

  /** Compose: merge another context transform. Suppression wins. */
  inject(other: CTransform): CTransform {
    return new CTransform(
      `${this.name}+${other.name}`,
      { ...this.config, ...other.config },
      this.suppressHistory || other.suppressHistory,
      [...this.children, other],
    );
  }
}

/**
 * C namespace — context engineering factories.
 */
export class C {
  /** Suppress all conversation history. */
  static none(): CTransform {
    return new CTransform("none", {}, true);
  }

  /** Default ADK behavior (keep all history). */
  static default_(): CTransform {
    return new CTransform("default", {}, false);
  }

  /** Only user messages. */
  static userOnly(): CTransform {
    return new CTransform("user_only", { filter: "user" }, true);
  }

  /** Last N turn-pairs. */
  static window(n = 5): CTransform {
    return new CTransform(`window(${n})`, { window: n }, true);
  }

  /** Inject state keys as context (neutral — keeps history). */
  static fromState(...keys: string[]): CTransform {
    return new CTransform(`from_state(${keys.join(",")})`, { stateKeys: keys }, false);
  }

  /** Template with {key} placeholders. */
  static template(text: string): CTransform {
    return new CTransform("template", { template: text }, false);
  }

  /** Inject scratchpad notes. */
  static notes(key = "notes"): CTransform {
    return new CTransform(`notes(${key})`, { notesKey: key }, false);
  }

  /** Filter to include only messages from named agents. */
  static fromAgents(...names: string[]): CTransform {
    return new CTransform(`from_agents(${names.join(",")})`, { agents: names }, true);
  }

  /** Exclude messages from named agents. */
  static excludeAgents(...names: string[]): CTransform {
    return new CTransform(`exclude_agents(${names.join(",")})`, { excludeAgents: names }, true);
  }

  /** Hard turn limit. */
  static truncate(maxTurns: number): CTransform {
    return new CTransform(`truncate(${maxTurns})`, { maxTurns }, true);
  }

  /** Conditional context transform. */
  static when(
    predicate: (state: Record<string, unknown>) => boolean,
    transform: CTransform,
  ): CTransform {
    return new CTransform(`when(${transform.name})`, {
      condition: predicate,
      child: transform,
    }, transform.suppressHistory);
  }
}

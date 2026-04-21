/**
 * P — Prompt composition namespace.
 *
 * Factory methods returning composable prompt sections.
 *
 * Operators (see `shared/parity.toml` for the cross-language contract):
 *   a.union(b)  → section set union. Canonical section order is preserved
 *                 (role → context → task → constraint → format → example)
 *                 regardless of the order you `.union()` them.
 *                 Mirrors Python `a | b`.
 *   a.pipe(b)   → post-process the rendered output through b.
 *                 Mirrors Python `a >> b`.
 *   a.attachTo(builder) → equivalent to Python's `a >> builder`.
 *                         Calls `builder.instruct(a)`.
 *
 * Usage:
 *   agent.instruct(
 *     P.role("Senior analyst")
 *       .union(P.task("Analyze the data"))
 *       .union(P.constraint("Be concise", "Use tables"))
 *   )
 */

import type { State } from "../core/types.js";
import type { BuilderBase } from "../core/builder-base.js";

// Section ordering priority
const SECTION_ORDER: Record<string, number> = {
  Role: 0,
  Context: 1,
  Task: 2,
  Constraints: 3,
  "Output Format": 4,
  Example: 5,
};

/** A composable prompt section descriptor. */
export class PTransform {
  constructor(
    public readonly section: string,
    public readonly text: string,
    public readonly children: PTransform[] = [],
    public readonly meta: Record<string, unknown> = {},
  ) {}

  /** Union: add another section. Mirrors Python ``|``. */
  union(other: PTransform): PTransform {
    return new PTransform(this.section, this.text, [...this.children, other], this.meta);
  }

  /** Pipe: transform the rendered output. */
  pipe(other: PTransform): PTransform {
    return new PTransform(`${this.section}|${other.section}`, "", [this, other]);
  }

  /**
   * Attach this prompt composition to a builder's instruction. Mirrors
   * Python's ``P.role() + P.task() >> Agent(...)``.
   */
  attachTo<B extends BuilderBase>(builder: B): B {
    const setter = (builder as unknown as { instruct: (v: unknown) => B }).instruct;
    if (typeof setter !== "function") {
      throw new TypeError(
        `PTransform.attachTo: builder has no .instruct() method (builder is ${builder.constructor.name})`,
      );
    }
    return setter.call(builder, this);
  }

  /** Render the full prompt string with sections ordered canonically. */
  render(state?: State): string {
    const allSections = this._collectSections(state);
    // Sort by canonical section order
    allSections.sort((a, b) => {
      const orderA = SECTION_ORDER[a.section] ?? 99;
      const orderB = SECTION_ORDER[b.section] ?? 99;
      return orderA - orderB;
    });
    return allSections.map((s) => s._renderSingle(state)).join("\n\n");
  }

  /** Compute a fingerprint for caching. */
  fingerprint(): string {
    return this.render();
  }

  toString(): string {
    return this.render();
  }

  /** Collect all leaf sections recursively. */
  private _collectSections(state?: State): PTransform[] {
    const leaves: PTransform[] = [];
    if (this.text) {
      leaves.push(this);
    }
    for (const child of this.children) {
      leaves.push(...child._collectSections(state));
    }
    return leaves;
  }

  /** Render a single section block. */
  private _renderSingle(_state?: State): string {
    if (this.section) {
      return `## ${this.section}\n${this.text}`;
    }
    return this.text;
  }
}

/**
 * P namespace — prompt composition factories.
 *
 * All 19 methods from the Python P namespace.
 */
export class P {
  // ------------------------------------------------------------------
  // Core sections
  // ------------------------------------------------------------------

  /** Agent persona / role. */
  static role(text: string): PTransform {
    return new PTransform("Role", text);
  }

  /** Background context. */
  static context(text: string): PTransform {
    return new PTransform("Context", text);
  }

  /** Primary objective / task. */
  static task(text: string): PTransform {
    return new PTransform("Task", text);
  }

  /** Constraints and rules (multiple strings → bullet list). */
  static constraint(...rules: string[]): PTransform {
    const text = rules.map((r) => `- ${r}`).join("\n");
    return new PTransform("Constraints", text);
  }

  /** Output format specification. */
  static format(text: string): PTransform {
    return new PTransform("Output Format", text);
  }

  /** Few-shot example (freeform or structured). */
  static example(opts: { text?: string; input?: string; output?: string }): PTransform {
    let text: string;
    if (opts.text) {
      text = opts.text;
    } else {
      text = `Input: ${opts.input ?? ""}\nOutput: ${opts.output ?? ""}`;
    }
    return new PTransform("Example", text);
  }

  /** Custom named section. */
  static section(name: string, text: string): PTransform {
    return new PTransform(name, text);
  }

  // ------------------------------------------------------------------
  // Dynamic / state-aware
  // ------------------------------------------------------------------

  /** Conditional block inclusion. */
  static when(predicate: (state: State) => boolean, block: PTransform): PTransform {
    return new PTransform("", "", [block], { condition: predicate });
  }

  /** Read keys from state and format as context. */
  static fromState(...keys: string[]): PTransform {
    return new PTransform("", "", [], { fromState: keys });
  }

  /**
   * Template with {key}, {key?} (optional), and {ns:key} placeholders.
   * Resolved at runtime from agent state.
   */
  static template(text: string): PTransform {
    return new PTransform("", text, [], { isTemplate: true });
  }

  // ------------------------------------------------------------------
  // Section manipulation
  // ------------------------------------------------------------------

  /** Override section ordering. */
  static reorder(...sectionNames: string[]): PTransform {
    return new PTransform("", "", [], { reorder: sectionNames });
  }

  /** Keep only named sections (filter others). */
  static only(...sectionNames: string[]): PTransform {
    return new PTransform("", "", [], { only: new Set(sectionNames) });
  }

  /** Remove named sections. */
  static without(...sectionNames: string[]): PTransform {
    return new PTransform("", "", [], { without: new Set(sectionNames) });
  }

  // ------------------------------------------------------------------
  // LLM-powered transforms
  // ------------------------------------------------------------------

  /** LLM-compress verbose prompts. */
  static compress(opts?: { maxTokens?: number }): PTransform {
    return new PTransform("", "", [], {
      compress: true,
      maxTokens: opts?.maxTokens ?? 500,
    });
  }

  /** Adapt tone/complexity for audience. */
  static adapt(audience: string): PTransform {
    return new PTransform("", "", [], { adapt: audience });
  }

  // ------------------------------------------------------------------
  // Structural
  // ------------------------------------------------------------------

  /** Wrap block in defensive scaffolding. */
  static scaffolded(
    block: PTransform,
    opts?: { preamble?: string; postamble?: string },
  ): PTransform {
    const preamble = opts?.preamble ?? "Follow these instructions carefully:";
    const postamble = opts?.postamble ?? "Now proceed with the above instructions.";
    return new PTransform("", `${preamble}\n\n${block.render()}\n\n${postamble}`);
  }

  /** Attach version metadata + fingerprint. */
  static versioned(block: PTransform, tag = ""): PTransform {
    const fp = block.fingerprint();
    return new PTransform("", block.render(), [], {
      version: tag,
      fingerprint: fp,
    });
  }

  // ------------------------------------------------------------------
  // A2UI
  // ------------------------------------------------------------------

  /** Inject A2UI component catalog schema into prompt. */
  static uiSchema(opts?: { catalog?: string; examples?: boolean }): PTransform {
    return new PTransform("UI Schema", "", [], {
      uiSchema: true,
      catalog: opts?.catalog ?? "basic",
      examples: opts?.examples ?? true,
    });
  }
}

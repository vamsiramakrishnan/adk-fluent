/**
 * P — Prompt composition namespace.
 *
 * Factory methods returning composable prompt sections.
 * Section order: role → context → task → constraint → format → example.
 *
 * Usage:
 *   agent.instruct(
 *     P.role("Senior analyst")
 *       .add(P.task("Analyze the data"))
 *       .add(P.constraint("Be concise", "Use tables"))
 *   )
 */

/** A composable prompt section. */
export class PTransform {
  constructor(
    public readonly section: string,
    public readonly text: string,
    public readonly children: PTransform[] = [],
  ) {}

  /** Compose: add another section to this prompt. */
  add(other: PTransform): PTransform {
    return new PTransform(this.section, this.text, [
      ...this.children,
      other,
    ]);
  }

  /** Render the full prompt string. */
  render(): string {
    const parts: string[] = [];
    if (this.text) {
      if (this.section) {
        parts.push(`## ${this.section}\n${this.text}`);
      } else {
        parts.push(this.text);
      }
    }
    for (const child of this.children) {
      parts.push(child.render());
    }
    return parts.join("\n\n");
  }

  /** Convert to string (for passing to .instruct()). */
  toString(): string {
    return this.render();
  }
}

/**
 * P namespace — prompt composition factories.
 */
export class P {
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

  /** Constraints and rules. */
  static constraint(...rules: string[]): PTransform {
    const text = rules.map((r) => `- ${r}`).join("\n");
    return new PTransform("Constraints", text);
  }

  /** Output format specification. */
  static format(text: string): PTransform {
    return new PTransform("Output Format", text);
  }

  /** Few-shot example. */
  static example(input: string, output: string): PTransform {
    return new PTransform(
      "Example",
      `Input: ${input}\nOutput: ${output}`,
    );
  }

  /** Custom named section. */
  static section(name: string, text: string): PTransform {
    return new PTransform(name, text);
  }

  /** Template with {key} placeholders (resolved at runtime from state). */
  static template(text: string): PTransform {
    return new PTransform("", text);
  }
}

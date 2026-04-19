/**
 * flux DSL — authoring types.
 *
 * Authors import from here:
 *     import { defineComponent, z } from "../dsl/types";
 *
 * ONE component per .spec.ts file. The default export MUST be a
 * ComponentSpec produced by defineComponent(...).
 *
 * The DSL is a pure TypeScript surface. At build time, the flux
 * generator imports each spec file and serializes its default export to
 * JSON; that JSON is validated against component.schema.json, then
 * emitted into catalog.json.
 */

// Zod is re-exported so spec authors never need to add it to their
// imports. The generator's tsconfig provides zod as an ambient dep.
export { z } from "zod";
import type { ZodTypeAny } from "zod";

// ---------------------------------------------------------------------------
// Token reference type
// ---------------------------------------------------------------------------

/** A token reference, dotted path prefixed with `$`. */
export type TokenRef = `$${string}`;

/** A style value is either a token reference, a raw string, or a number. */
export type StyleValue = TokenRef | string | number | boolean;

/** A style object is a flat map. No nesting; compound shapes live in variants. */
export type StyleObject = Record<string, StyleValue>;

// ---------------------------------------------------------------------------
// Slots
// ---------------------------------------------------------------------------

/**
 * A named insertion point inside a component. `kind` names the
 * acceptable child component(s) — either basic-catalog (`"Text"`) or
 * flux (`"FluxBadge"`). Multiple kinds may be listed.
 */
export interface Slot {
  readonly kind: string | readonly string[];
  readonly required?: boolean;
  readonly max?: number;
  readonly description?: string;
}

export type Slots = Readonly<Record<string, Slot>>;

// ---------------------------------------------------------------------------
// Variants
// ---------------------------------------------------------------------------

export type Variant = Readonly<Record<string, StyleObject>>;
export type Variants = Readonly<Record<string, Variant>>;

export interface CompoundVariant {
  readonly style: StyleObject;
  /** Any additional string keys are variant-dimension matchers. */
  readonly [k: string]: string | StyleObject | undefined;
}

// ---------------------------------------------------------------------------
// Accessibility
// ---------------------------------------------------------------------------

export interface AccessibilitySpec {
  readonly label: "required" | "optional" | "none";
  readonly role?: string;
  readonly keyboard?: ReadonlyArray<{ readonly key: string; readonly action: string }>;
}

// ---------------------------------------------------------------------------
// LLM metadata
// ---------------------------------------------------------------------------

export interface LLMExample {
  readonly code: string;
  readonly caption: string;
}

export interface LLMAntiPattern {
  readonly code: string;
  readonly reason: string;
}

export interface LLMBudget {
  readonly children: number;
  readonly siblings: number;
  readonly depth?: number;
}

export interface LLMMetadata {
  readonly description: string;
  readonly tags?: readonly string[];
  readonly examples: readonly LLMExample[];
  readonly antiPatterns?: readonly LLMAntiPattern[];
  readonly budget: LLMBudget;
}

// ---------------------------------------------------------------------------
// Renderer mapping
// ---------------------------------------------------------------------------

export interface FallbackMapping {
  /** The basic-catalog component to degrade to. */
  readonly component: string;
  /** Prop renames flux-prop to basic-prop. Omitted props are dropped. */
  readonly map?: Readonly<Record<string, string>>;
  readonly notes?: string;
}

export interface RendererMapping {
  /** Repo-relative path to the React component file. */
  readonly react: string;
  readonly fallback: FallbackMapping;
}

// ---------------------------------------------------------------------------
// Category
// ---------------------------------------------------------------------------

export type ComponentCategory = "primitive" | "compound" | "intent";

// ---------------------------------------------------------------------------
// Author-facing ComponentSpec
// ---------------------------------------------------------------------------

export interface ComponentSpec {
  readonly name: string; // must start with "Flux"
  readonly extends: string; // basic-catalog component
  readonly category: ComponentCategory;
  readonly schema: ZodTypeAny; // Zod schema — compiled to JSON Schema by emit
  readonly slots?: Slots;
  readonly variants?: Variants;
  readonly compoundVariants?: readonly CompoundVariant[];
  readonly defaultVariants?: Readonly<Record<string, string>>;
  readonly tokens: readonly string[];
  readonly accessibility: AccessibilitySpec;
  readonly llm: LLMMetadata;
  readonly renderer: RendererMapping;
}

/**
 * Author entry point. Returns the spec verbatim after cheap invariant
 * checks so bugs surface at `tsc` time rather than in generator output.
 */
export function defineComponent<S extends ComponentSpec>(spec: S): S {
  // Invariant: name prefix
  if (!spec.name.startsWith("Flux")) {
    throw new Error(`[flux DSL] component.name must start with "Flux"; got: ${spec.name}`);
  }
  // Invariant: interactive components must declare a11y label
  const interactive = ["Button", "TextField", "CheckBox", "ChoicePicker", "Slider", "DateTimeInput"];
  if (interactive.includes(spec.extends) && spec.accessibility.label !== "required") {
    throw new Error(
      `[flux DSL] ${spec.name} extends interactive ${spec.extends}; accessibility.label must be "required".`,
    );
  }
  // Invariant: llm examples non-empty
  if (spec.llm.examples.length === 0) {
    throw new Error(`[flux DSL] ${spec.name}: llm.examples must have at least 1 entry.`);
  }
  // Invariant: variant references
  if (spec.defaultVariants && spec.variants) {
    for (const [dim, val] of Object.entries(spec.defaultVariants)) {
      if (!spec.variants[dim]) {
        throw new Error(`[flux DSL] ${spec.name}: defaultVariants.${dim} has no matching variants.${dim}`);
      }
      if (!spec.variants[dim][val]) {
        throw new Error(`[flux DSL] ${spec.name}: defaultVariants.${dim}='${val}' is not a declared variant.`);
      }
    }
  }
  return spec;
}

/** Convenience: declare a token reference as a typed string literal. */
export function token(path: string): TokenRef {
  return `$${path}` as TokenRef;
}

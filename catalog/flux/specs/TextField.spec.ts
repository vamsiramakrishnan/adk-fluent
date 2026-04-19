/**
 * FluxTextField — single-line text input with size × state variants.
 *
 * Extends the basic-catalog `TextField`, which makes the component
 * interactive and forces `accessibility.label: "required"` via the DSL
 * invariant. `type` covers the common HTML input kinds; `state` is the
 * visual validation status (default / error / success / warning); `size`
 * scales padding + typography.
 *
 * Slots:
 *  - `leadingIcon`  — optional affordance (e.g. search magnifier).
 *  - `trailingIcon` — optional affordance (e.g. visibility toggle).
 *  - `helper`       — inline Text node rendered below the input. Not
 *                     required: authors can pass plain `helper` / `error`
 *                     strings without instantiating a child component.
 *
 * Keyboard: `Tab` moves focus; `Enter` submits the enclosing form.
 */

import { defineComponent, z } from "../dsl/types";

export default defineComponent({
  name: "FluxTextField",
  extends: "TextField",
  category: "primitive",

  // ---------------------------------------------------------------------
  // Schema — compiled to JSON Schema by the emitter.
  // ---------------------------------------------------------------------
  schema: z.object({
    component: z.literal("FluxTextField"),
    id: z.string(),

    // Content
    value: z.string().optional(),
    placeholder: z.string().optional(),
    type: z
      .enum(["text", "email", "password", "number", "search", "tel", "url"])
      .default("text"),

    // Variant dimensions
    size: z.enum(["sm", "md", "lg"]).default("md"),
    state: z.enum(["default", "error", "success", "warning"]).default("default"),

    // Behavior
    disabled: z.boolean().optional(),
    readonly: z.boolean().optional(),
    required: z.boolean().optional(),
    maxLength: z.number().int().positive().optional(),

    // Helper + error text (plain-string convenience — slot wins when set).
    helper: z.string().optional(),
    error: z.string().optional(),

    // Accessibility (required by DSL invariant).
    accessibility: z.object({
      label: z.string(),
      description: z.string().optional(),
    }),

    // Slots by id reference
    leadingIcon: z.string().optional(),
    trailingIcon: z.string().optional(),
  }),

  // ---------------------------------------------------------------------
  // Slots
  // ---------------------------------------------------------------------
  slots: {
    leadingIcon: { kind: "Icon", required: false },
    trailingIcon: { kind: "Icon", required: false },
    helper: { kind: "Text", required: false },
  },

  // ---------------------------------------------------------------------
  // Tokens referenced (build-fails on any missing path)
  // ---------------------------------------------------------------------
  tokens: [
    "color.bg.surface",
    "color.border.default",
    "color.border.danger",
    "color.success.solid",
    "color.warning.7",
    "color.text.primary",
    "color.text.danger",
    "space.2",
    "space.3",
    "space.4",
    "radius.md",
    "radius.lg",
    "typography.size.sm",
    "typography.size.md",
    "typography.size.lg",
  ],

  // ---------------------------------------------------------------------
  // Variant recipe (size x state)
  // ---------------------------------------------------------------------
  variants: {
    size: {
      sm: {
        paddingBlock: "$space.2",
        paddingInline: "$space.3",
        fontSize: "$typography.size.sm",
        borderRadius: "$radius.md",
      },
      md: {
        paddingBlock: "$space.2",
        paddingInline: "$space.3",
        fontSize: "$typography.size.md",
        borderRadius: "$radius.md",
      },
      lg: {
        paddingBlock: "$space.3",
        paddingInline: "$space.4",
        fontSize: "$typography.size.lg",
        borderRadius: "$radius.lg",
      },
    },
    state: {
      default: {
        backgroundColor: "$color.bg.surface",
        borderColor: "$color.border.default",
        color: "$color.text.primary",
      },
      error: {
        backgroundColor: "$color.bg.surface",
        borderColor: "$color.border.danger",
        color: "$color.text.primary",
      },
      success: {
        backgroundColor: "$color.bg.surface",
        borderColor: "$color.success.solid",
        color: "$color.text.primary",
      },
      warning: {
        backgroundColor: "$color.bg.surface",
        borderColor: "$color.warning.7",
        color: "$color.text.primary",
      },
    },
  },

  // ---------------------------------------------------------------------
  // compoundVariants — state=error + size=lg bumps helper typography.
  // ---------------------------------------------------------------------
  compoundVariants: [
    {
      state: "error",
      size: "lg",
      style: {
        fontSize: "$typography.size.lg",
        color: "$color.text.danger",
      },
    },
  ],

  defaultVariants: {
    size: "md",
    state: "default",
  },

  // ---------------------------------------------------------------------
  // Accessibility (required for interactive components)
  // ---------------------------------------------------------------------
  accessibility: {
    label: "required",
    role: "textbox",
    keyboard: [
      { key: "Tab", action: "focus" },
      { key: "Enter", action: "submit" },
    ],
  },

  // ---------------------------------------------------------------------
  // LLM metadata
  // ---------------------------------------------------------------------
  llm: {
    description:
      "A single-line text input. Use `type` to pick the semantic kind (email, password, number, …); use `state` to surface validation status. Always set `accessibility.label` — screen readers need it even when a visible placeholder exists.",
    tags: ["interactive", "form", "input", "validation"],
    examples: [
      {
        code: `UI.text_field("email", type="email", placeholder="you@example.com")`,
        caption: "Basic email field with placeholder.",
      },
      {
        code: `UI.text_field("password", type="password", helper="At least 12 characters.")`,
        caption: "Password field with helper text.",
      },
      {
        code: `UI.text_field("age", type="number", state="error", error="Must be 18+")`,
        caption: "Numeric field surfacing a validation error.",
      },
    ],
    antiPatterns: [
      {
        code: `UI.text_field("email")   # no accessibility.label`,
        reason:
          "accessibility.label is required — placeholders are not a11y labels.",
      },
      {
        code: `UI.text_field("token", type="password")   # masking a non-secret`,
        reason:
          "type=password hides input; reserve it for actual credentials, not long IDs the user may need to paste.",
      },
    ],
    budget: { children: 0, siblings: 8, depth: 6 },
  },

  // ---------------------------------------------------------------------
  // Renderer mapping
  // ---------------------------------------------------------------------
  renderer: {
    react: "./renderers/react/FluxTextField.tsx",
    fallback: {
      component: "TextField",
      map: {
        value: "value",
        placeholder: "placeholder",
      },
      notes:
        "Basic renderers drop size / state / helper / icons — only the raw input with a placeholder survives.",
    },
  },
});

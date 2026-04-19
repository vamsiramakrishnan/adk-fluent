/**
 * FluxButton — the reference flux component spec.
 *
 * This file exercises every DSL feature:
 *  - Zod schema with enums, optional slots, and accessibility props
 *  - Multi-dimensional variant recipe (tone x size x emphasis)
 *  - compoundVariants for dimension intersections
 *  - Slots (leadingIcon, label, trailingIcon) typed by basic-catalog kind
 *  - Token references ONLY (never raw hex)
 *  - Accessibility contract (label: required) enforced by defineComponent
 *  - LLM metadata (examples + antiPatterns + budget)
 *  - Renderer mapping with fallback to basic-catalog Button
 *
 * Every other flux component follows this template.
 */

import { defineComponent, z } from "../dsl/types";

export default defineComponent({
  name: "FluxButton",
  extends: "Button",
  category: "primitive",

  // ---------------------------------------------------------------------
  // Schema — compiled to JSON Schema by the emitter.
  // ---------------------------------------------------------------------
  schema: z.object({
    component: z.literal("FluxButton"),
    id: z.string(),

    // Content: either a simple label, or fill via slots.
    label: z.string().optional(),

    // Variant dimensions (echoed back by the LLM; validated against
    // the variants map below at runtime by the flux guard).
    tone: z.enum(["neutral", "primary", "danger", "success"]).default("neutral"),
    size: z.enum(["sm", "md", "lg"]).default("md"),
    emphasis: z.enum(["solid", "soft", "outline", "ghost"]).default("solid"),

    // Behavior
    action: z.object({
      event: z.object({
        name: z.string(),
        context: z.record(z.string(), z.unknown()).optional(),
      }),
    }),
    disabled: z.boolean().optional(),
    loading: z.boolean().optional(),

    // Accessibility (required by DSL invariant — re-declared here so the
    // JSON Schema can enforce it at render-time too).
    accessibility: z.object({
      label: z.string(),
      description: z.string().optional(),
    }),

    // Slots by id reference (A2UI rule: children by id, never inline).
    leadingIcon: z.string().optional(),
    trailingIcon: z.string().optional(),
  }),

  // ---------------------------------------------------------------------
  // Slots
  // ---------------------------------------------------------------------
  slots: {
    leadingIcon: { kind: "Icon", required: false },
    trailingIcon: { kind: "Icon", required: false },
  },

  // ---------------------------------------------------------------------
  // Tokens referenced (build-fails on any missing path)
  // ---------------------------------------------------------------------
  tokens: [
    "color.primary.solid",
    "color.primary.solidHover",
    "color.primary.subtle",
    "color.primary.subtleHover",
    "color.bg.subtle",
    "color.border.default",
    "color.border.focus",
    "color.danger.solid",
    "color.danger.subtle",
    "color.success.solid",
    "color.text.onBrand",
    "color.text.primary",
    "color.text.muted",
    "color.text.danger",
    "space.2",
    "space.3",
    "space.4",
    "radius.md",
    "radius.lg",
    "shadow.sm",
    "shadow.focus",
    "typography.size.sm",
    "typography.size.md",
    "typography.size.lg",
    "typography.weight.medium",
    "motion.duration.fast",
    "motion.easing.standard",
  ],

  // ---------------------------------------------------------------------
  // Variant recipe (tone x size x emphasis)
  // ---------------------------------------------------------------------
  variants: {
    tone: {
      neutral: {
        backgroundColor: "$color.bg.subtle",
        color: "$color.text.primary",
        borderColor: "$color.border.default",
      },
      primary: {
        backgroundColor: "$color.primary.solid",
        color: "$color.text.onBrand",
        borderColor: "$color.primary.solid",
      },
      danger: {
        backgroundColor: "$color.danger.solid",
        color: "$color.text.onBrand",
        borderColor: "$color.danger.solid",
      },
      success: {
        backgroundColor: "$color.success.solid",
        color: "$color.text.onBrand",
        borderColor: "$color.success.solid",
      },
    },
    size: {
      sm: {
        paddingBlock: "$space.2",
        paddingInline: "$space.3",
        fontSize: "$typography.size.sm",
        borderRadius: "$radius.md",
      },
      md: {
        paddingBlock: "$space.2",
        paddingInline: "$space.4",
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
    emphasis: {
      solid: {
        borderWidth: "0px",
        boxShadow: "$shadow.sm",
      },
      soft: {
        backgroundColor: "$color.primary.subtle",
        color: "$color.text.primary",
        borderWidth: "0px",
      },
      outline: {
        backgroundColor: "transparent",
        borderWidth: "1px",
        color: "$color.text.primary",
      },
      ghost: {
        backgroundColor: "transparent",
        borderWidth: "0px",
        color: "$color.text.primary",
      },
    },
  },

  // ---------------------------------------------------------------------
  // compoundVariants — style applied when multiple dims match.
  // ---------------------------------------------------------------------
  compoundVariants: [
    {
      tone: "danger",
      emphasis: "outline",
      style: {
        borderColor: "$color.danger.solid",
        color: "$color.text.danger",
      },
    },
    {
      tone: "primary",
      emphasis: "soft",
      style: {
        backgroundColor: "$color.primary.subtle",
        color: "$color.text.primary",
      },
    },
    {
      tone: "neutral",
      emphasis: "ghost",
      style: {
        color: "$color.text.muted",
      },
    },
  ],

  defaultVariants: {
    tone: "neutral",
    size: "md",
    emphasis: "solid",
  },

  // ---------------------------------------------------------------------
  // Accessibility (required for interactive components)
  // ---------------------------------------------------------------------
  accessibility: {
    label: "required",
    role: "button",
    keyboard: [
      { key: "Enter", action: "activate" },
      { key: "Space", action: "activate" },
    ],
  },

  // ---------------------------------------------------------------------
  // LLM metadata (drives T.search, G.a2ui, prompt injection)
  // ---------------------------------------------------------------------
  llm: {
    description:
      "A clickable button that dispatches a server action. Use tone=primary for the single call-to-action per surface; tone=danger for destructive operations; tone=neutral elsewhere.",
    tags: ["interactive", "cta", "form", "action"],
    examples: [
      {
        code: `UI.button("Save", tone="primary", size="md", action="save_form")`,
        caption: "Standard primary CTA.",
      },
      {
        code: `UI.button("Delete", tone="danger", emphasis="outline", action="confirm_delete")`,
        caption: "Destructive outline button.",
      },
      {
        code: `UI.button("Undo", tone="neutral", emphasis="ghost", size="sm", action="undo")`,
        caption: "Ghost secondary action.",
      },
    ],
    antiPatterns: [
      {
        code: `UI.row([UI.button("Save", tone="primary"), UI.button("Ship", tone="primary")])`,
        reason: "Only one primary CTA per surface. Second button should be tone=neutral.",
      },
      {
        code: `UI.button("Click me")   # no action`,
        reason: "Every FluxButton requires a non-empty action.",
      },
      {
        code: `UI.button("OK", tone="danger")   # non-destructive copy`,
        reason: "tone=danger signals destructive intent. Don't use it for confirmations.",
      },
    ],
    budget: { children: 0, siblings: 8, depth: 6 },
  },

  // ---------------------------------------------------------------------
  // Renderer mapping
  // ---------------------------------------------------------------------
  renderer: {
    react: "./renderers/react/FluxButton.tsx",
    fallback: {
      component: "Button",
      map: {
        label: "child",
        tone: "variant",
        action: "action",
      },
      notes:
        "Basic renderers lose size + emphasis + tone=success; degrades to primary or default variant only. Labels are wrapped in a generated Text child at compile time.",
    },
  },
});

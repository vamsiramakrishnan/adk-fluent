/**
 * FluxBadge — compact status / count label.
 *
 * The DSL's minimum-viable example, polished into a real spec. Tones
 * match FluxButton (neutral / primary / success / warning / danger);
 * `variant` picks between a subtle fill and a solid fill; `size` scales
 * the badge for inline or block contexts.
 *
 * Not interactive — a badge is a label, not a button. If authors need
 * click behavior they should reach for `UI.button(..., size="sm")`.
 */

import { defineComponent, z } from "../dsl/types";

export default defineComponent({
  name: "FluxBadge",
  extends: "Text",
  category: "primitive",

  // ---------------------------------------------------------------------
  // Schema
  // ---------------------------------------------------------------------
  schema: z.object({
    component: z.literal("FluxBadge"),
    id: z.string(),

    // Content
    label: z.string(),

    // Variant dimensions
    tone: z
      .enum(["neutral", "primary", "success", "warning", "danger"])
      .default("neutral"),
    variant: z.enum(["subtle", "solid"]).default("subtle"),
    size: z.enum(["xs", "sm", "md"]).default("sm"),

    // Accessibility
    accessibility: z
      .object({
        label: z.string(),
        description: z.string().optional(),
      })
      .optional(),
  }),

  // ---------------------------------------------------------------------
  // Tokens referenced
  // ---------------------------------------------------------------------
  tokens: [
    "color.bg.subtle",
    "color.primary.subtle",
    "color.primary.solid",
    "color.success.subtle",
    "color.success.solid",
    "color.warning.3",
    "color.warning.9",
    "color.danger.subtle",
    "color.danger.solid",
    "color.text.primary",
    "color.text.muted",
    "color.text.onBrand",
    "space.0_5",
    "space.1",
    "space.1_5",
    "space.2",
    "radius.sm",
    "radius.full",
    "typography.size.xs",
    "typography.size.sm",
    "typography.weight.medium",
  ],

  // ---------------------------------------------------------------------
  // Variant recipe (tone x variant x size)
  // ---------------------------------------------------------------------
  variants: {
    tone: {
      neutral: {
        backgroundColor: "$color.bg.subtle",
        color: "$color.text.muted",
      },
      primary: {
        backgroundColor: "$color.primary.subtle",
        color: "$color.text.primary",
      },
      success: {
        backgroundColor: "$color.success.subtle",
        color: "$color.success.solid",
      },
      warning: {
        backgroundColor: "$color.warning.3",
        color: "$color.warning.9",
      },
      danger: {
        backgroundColor: "$color.danger.subtle",
        color: "$color.danger.solid",
      },
    },
    variant: {
      subtle: {
        borderRadius: "$radius.sm",
        fontWeight: "$typography.weight.medium",
      },
      solid: {
        borderRadius: "$radius.full",
        fontWeight: "$typography.weight.medium",
      },
    },
    size: {
      xs: {
        paddingBlock: "$space.0_5",
        paddingInline: "$space.1",
        fontSize: "$typography.size.xs",
      },
      sm: {
        paddingBlock: "$space.0_5",
        paddingInline: "$space.1_5",
        fontSize: "$typography.size.xs",
      },
      md: {
        paddingBlock: "$space.1",
        paddingInline: "$space.2",
        fontSize: "$typography.size.sm",
      },
    },
  },

  // ---------------------------------------------------------------------
  // compoundVariants — solid primary flips to onBrand text.
  // ---------------------------------------------------------------------
  compoundVariants: [
    {
      tone: "primary",
      variant: "solid",
      style: {
        backgroundColor: "$color.primary.solid",
        color: "$color.text.onBrand",
      },
    },
    {
      tone: "success",
      variant: "solid",
      style: {
        backgroundColor: "$color.success.solid",
        color: "$color.text.onBrand",
      },
    },
    {
      tone: "danger",
      variant: "solid",
      style: {
        backgroundColor: "$color.danger.solid",
        color: "$color.text.onBrand",
      },
    },
  ],

  defaultVariants: {
    tone: "neutral",
    variant: "subtle",
    size: "sm",
  },

  // ---------------------------------------------------------------------
  // Accessibility
  // ---------------------------------------------------------------------
  accessibility: {
    label: "optional",
    role: "status",
  },

  // ---------------------------------------------------------------------
  // LLM metadata
  // ---------------------------------------------------------------------
  llm: {
    description:
      "Compact label for status, counts, or tags. Not clickable — if the affordance needs to trigger an action, use a small button instead. Tones align with the rest of the catalog (neutral/primary/success/warning/danger).",
    tags: ["label", "status", "count", "tag"],
    examples: [
      {
        code: `UI.badge("New", tone="primary", variant="solid")`,
        caption: "Solid primary tag for highlighted items.",
      },
      {
        code: `UI.badge("Live", tone="success", size="md")`,
        caption: "Subtle success label in the larger size.",
      },
    ],
    antiPatterns: [
      {
        code: `UI.badge("Click me", action="open")`,
        reason:
          "Badges are not interactive. Use UI.button with size=sm for a clickable chip.",
      },
      {
        code: `UI.badge("Download the Q3 2024 revenue and expenses report here", tone="primary")`,
        reason:
          "Badge copy must be short (ideally ≤3 words). Long copy belongs in Text, not a badge.",
      },
    ],
    budget: { children: 0, siblings: 12, depth: 6 },
  },

  // ---------------------------------------------------------------------
  // Renderer mapping
  // ---------------------------------------------------------------------
  renderer: {
    react: "./renderers/react/FluxBadge.tsx",
    fallback: {
      component: "Text",
      map: {
        label: "text",
      },
      notes:
        "Basic renderers drop tone + variant + size styling; the badge collapses to a short plain-text run.",
    },
  },
});

/**
 * FluxCard — header / body / footer surface container.
 *
 * Extends `Column` because its natural layout is vertical: optional
 * header, required body, optional footer. The `emphasis` dimension
 * controls visual weight (subtle / outline / elevated); `padding` picks
 * the interior spacing scale.
 *
 * Slots reference children by id. The body slot is required — a Card
 * without content is a box, not a card.
 */

import { defineComponent, z } from "../dsl/types";

export default defineComponent({
  name: "FluxCard",
  extends: "Column",
  category: "compound",

  // ---------------------------------------------------------------------
  // Schema
  // ---------------------------------------------------------------------
  schema: z.object({
    component: z.literal("FluxCard"),
    id: z.string(),

    // Variant dimensions
    emphasis: z.enum(["subtle", "outline", "elevated"]).default("subtle"),
    padding: z.enum(["sm", "md", "lg"]).default("md"),

    // Slots by id reference (body is required)
    header: z.string().optional(),
    body: z.string(),
    footer: z.string().optional(),

    // Accessibility
    accessibility: z
      .object({
        label: z.string(),
        description: z.string().optional(),
      })
      .optional(),
  }),

  // ---------------------------------------------------------------------
  // Slots
  // ---------------------------------------------------------------------
  slots: {
    header: { kind: ["Text", "Row"], required: false },
    body: { kind: ["Text", "Column", "Row"], required: true },
    footer: { kind: ["Text", "Row"], required: false },
  },

  // ---------------------------------------------------------------------
  // Tokens referenced
  // ---------------------------------------------------------------------
  tokens: [
    "color.bg.surface",
    "color.bg.subtle",
    "color.border.default",
    "space.3",
    "space.4",
    "space.6",
    "radius.md",
    "radius.lg",
    "radius.xl",
    "shadow.sm",
    "shadow.md",
  ],

  // ---------------------------------------------------------------------
  // Variant recipe (emphasis x padding)
  // ---------------------------------------------------------------------
  variants: {
    emphasis: {
      subtle: {
        backgroundColor: "$color.bg.subtle",
        borderWidth: "0px",
        boxShadow: "none",
        borderRadius: "$radius.md",
      },
      outline: {
        backgroundColor: "$color.bg.surface",
        borderWidth: "1px",
        borderColor: "$color.border.default",
        boxShadow: "none",
        borderRadius: "$radius.md",
      },
      elevated: {
        backgroundColor: "$color.bg.surface",
        borderWidth: "0px",
        boxShadow: "$shadow.md",
        borderRadius: "$radius.lg",
      },
    },
    padding: {
      sm: {
        paddingBlock: "$space.3",
        paddingInline: "$space.3",
      },
      md: {
        paddingBlock: "$space.4",
        paddingInline: "$space.4",
      },
      lg: {
        paddingBlock: "$space.6",
        paddingInline: "$space.6",
      },
    },
  },

  // ---------------------------------------------------------------------
  // compoundVariants — outline + lg padding wants a softer radius.
  // ---------------------------------------------------------------------
  compoundVariants: [
    {
      emphasis: "outline",
      padding: "lg",
      style: {
        borderRadius: "$radius.xl",
        boxShadow: "$shadow.sm",
      },
    },
  ],

  defaultVariants: {
    emphasis: "subtle",
    padding: "md",
  },

  // ---------------------------------------------------------------------
  // Accessibility
  // ---------------------------------------------------------------------
  accessibility: {
    label: "optional",
    role: "region",
  },

  // ---------------------------------------------------------------------
  // LLM metadata
  // ---------------------------------------------------------------------
  llm: {
    description:
      "A surface container with optional header, required body, and optional footer. Pick `emphasis=subtle` for secondary content, `outline` for delineated groups, `elevated` for prominent callouts. Children are referenced by id — never inline them.",
    tags: ["layout", "container", "surface"],
    examples: [
      {
        code: `UI.card(body="card_body_text")`,
        caption: "Simple card with body content.",
      },
      {
        code: `UI.card(emphasis="outline", padding="lg", header="card_title", body="card_body", footer="card_action_row")`,
        caption: "Outline card with header + body + footer action row.",
      },
    ],
    antiPatterns: [
      {
        code: `UI.card(body=other_card_id)`,
        reason:
          "Cards inside cards creates visual noise. Use a Stack or FluxStack for grouping within a single card.",
      },
    ],
    budget: { children: 3, siblings: 6, depth: 5 },
  },

  // ---------------------------------------------------------------------
  // Renderer mapping
  // ---------------------------------------------------------------------
  renderer: {
    react: "./renderers/react/FluxCard.tsx",
    fallback: {
      component: "Column",
      map: {
        header: "child",
        body: "child",
        footer: "child",
      },
      notes:
        "Basic renderers drop emphasis + padding tokens; the column stacks its slot children top-to-bottom with no surface styling.",
    },
  },
});

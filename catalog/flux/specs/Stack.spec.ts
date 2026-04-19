/**
 * FluxStack — layout primitive (direction × gap × align × justify).
 *
 * A thin wrapper over `Column` (the chosen `extends`) that swaps to
 * row-flow when `direction=horizontal`. Stack is intentionally a
 * primitive with no slots — children pass through so authors can group
 * arbitrary components with consistent spacing.
 *
 * No compound variants: the four dimensions are orthogonal and expose
 * 3 × 6 × 4 × 5 = 360 cells. Keeping compounds out of this spec avoids
 * combinatorial explosion; renderer handles the cross-product naturally
 * through CSS flexbox.
 */

import { defineComponent, z } from "../dsl/types";

export default defineComponent({
  name: "FluxStack",
  extends: "Column",
  category: "primitive",

  // ---------------------------------------------------------------------
  // Schema
  // ---------------------------------------------------------------------
  schema: z.object({
    component: z.literal("FluxStack"),
    id: z.string(),

    // Variant dimensions
    direction: z.enum(["vertical", "horizontal"]).default("vertical"),
    gap: z.enum(["1", "2", "3", "4", "6", "8"]).default("3"),
    align: z.enum(["start", "center", "end", "stretch"]).default("stretch"),
    justify: z
      .enum(["start", "center", "end", "between", "around"])
      .default("start"),

    // Behavior
    wrap: z.boolean().optional(),

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
    "space.1",
    "space.2",
    "space.3",
    "space.4",
    "space.6",
    "space.8",
  ],

  // ---------------------------------------------------------------------
  // Variant recipe (direction x gap x align x justify — orthogonal)
  // ---------------------------------------------------------------------
  variants: {
    direction: {
      vertical: {
        flexDirection: "column",
      },
      horizontal: {
        flexDirection: "row",
      },
    },
    gap: {
      "1": { gap: "$space.1" },
      "2": { gap: "$space.2" },
      "3": { gap: "$space.3" },
      "4": { gap: "$space.4" },
      "6": { gap: "$space.6" },
      "8": { gap: "$space.8" },
    },
    align: {
      start: { alignItems: "flex-start" },
      center: { alignItems: "center" },
      end: { alignItems: "flex-end" },
      stretch: { alignItems: "stretch" },
    },
    justify: {
      start: { justifyContent: "flex-start" },
      center: { justifyContent: "center" },
      end: { justifyContent: "flex-end" },
      between: { justifyContent: "space-between" },
      around: { justifyContent: "space-around" },
    },
  },

  defaultVariants: {
    direction: "vertical",
    gap: "3",
    align: "stretch",
    justify: "start",
  },

  // ---------------------------------------------------------------------
  // Accessibility
  // ---------------------------------------------------------------------
  accessibility: {
    label: "optional",
  },

  // ---------------------------------------------------------------------
  // LLM metadata
  // ---------------------------------------------------------------------
  llm: {
    description:
      "Layout primitive for arranging children with consistent spacing. Pick `direction=horizontal` for toolbars / button rows and `vertical` for forms / lists. `gap` picks a step on the 4-px spacing grid. Children pass through — Stack has no slots.",
    tags: ["layout", "flex", "primitive"],
    examples: [
      {
        code: `UI.stack(direction="horizontal", gap="4", align="center", children=[save_btn, cancel_btn])`,
        caption: "Horizontal button row with 16px gap.",
      },
      {
        code: `UI.stack(direction="vertical", gap="2", align="center", children=[title, subtitle])`,
        caption: "Vertically centered title stack.",
      },
    ],
    antiPatterns: [
      {
        code: `UI.stack(children=[single_child])`,
        reason:
          "Stack is for ≥2 children. A single child needs no wrapper — pass the component directly.",
      },
      {
        code: `UI.stack(children=[UI.stack(children=[UI.stack(children=[UI.stack(children=[...])])])])`,
        reason:
          "More than four nested stacks is a layout smell. Flatten or extract a Card / Column.",
      },
    ],
    budget: { children: 20, siblings: 12, depth: 8 },
  },

  // ---------------------------------------------------------------------
  // Renderer mapping
  // ---------------------------------------------------------------------
  renderer: {
    react: "./renderers/react/FluxStack.tsx",
    fallback: {
      component: "Column",
      map: {
        direction: "direction",
        gap: "gap",
      },
      notes:
        "Basic renderers only speak Column/Row — horizontal stacks degrade to a vertically stacked Column; gap/align/justify are dropped.",
    },
  },
});

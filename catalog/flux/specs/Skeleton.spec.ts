/**
 * FluxSkeleton — loading-state placeholder.
 *
 * Extends `Text` because its rendered shape most resembles a block of
 * text; in reality it's a shimmer-animated rectangle. Use `shape=text`
 * for content rows, `shape=circle` for avatars, and `shape=rect` for
 * card-shaped placeholders.
 *
 * Motion: shimmer uses the `slow` duration and the `emphasized` easing
 * curve so the animation feels intentional rather than jittery. Both
 * tokens are shared across flux-light and flux-dark.
 */

import { defineComponent, z } from "../dsl/types";

export default defineComponent({
  name: "FluxSkeleton",
  extends: "Text",
  category: "primitive",

  // ---------------------------------------------------------------------
  // Schema
  // ---------------------------------------------------------------------
  schema: z.object({
    component: z.literal("FluxSkeleton"),
    id: z.string(),

    // Shape + size
    shape: z.enum(["text", "circle", "rect"]).default("text"),
    size: z.enum(["xs", "sm", "md", "lg", "xl"]).default("md"),

    // Explicit overrides (optional)
    count: z.number().int().positive().optional(),
    width: z.string().optional(),
    height: z.string().optional(),

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
    "space.2",
    "space.3",
    "space.4",
    "space.5",
    "space.6",
    "space.8",
    "space.12",
    "radius.sm",
    "radius.md",
    "radius.full",
    "motion.duration.slow",
    "motion.easing.emphasized",
  ],

  // ---------------------------------------------------------------------
  // Variant recipe (shape x size)
  // ---------------------------------------------------------------------
  variants: {
    shape: {
      text: {
        backgroundColor: "$color.bg.subtle",
        borderRadius: "$radius.sm",
        animationDuration: "$motion.duration.slow",
        animationTimingFunction: "$motion.easing.emphasized",
      },
      circle: {
        backgroundColor: "$color.bg.subtle",
        borderRadius: "$radius.full",
        animationDuration: "$motion.duration.slow",
        animationTimingFunction: "$motion.easing.emphasized",
      },
      rect: {
        backgroundColor: "$color.bg.subtle",
        borderRadius: "$radius.md",
        animationDuration: "$motion.duration.slow",
        animationTimingFunction: "$motion.easing.emphasized",
      },
    },
    size: {
      xs: { height: "$space.2" },
      sm: { height: "$space.3" },
      md: { height: "$space.4" },
      lg: { height: "$space.6" },
      xl: { height: "$space.12" },
    },
  },

  // ---------------------------------------------------------------------
  // compoundVariants — circle+xl forces square dimensions.
  // ---------------------------------------------------------------------
  compoundVariants: [
    {
      shape: "circle",
      size: "xl",
      style: {
        width: "$space.12",
        height: "$space.12",
      },
    },
    {
      shape: "circle",
      size: "lg",
      style: {
        width: "$space.8",
        height: "$space.8",
      },
    },
    {
      shape: "circle",
      size: "md",
      style: {
        width: "$space.5",
        height: "$space.5",
      },
    },
  ],

  defaultVariants: {
    shape: "text",
    size: "md",
  },

  // ---------------------------------------------------------------------
  // Accessibility
  // ---------------------------------------------------------------------
  accessibility: {
    label: "optional",
    role: "presentation",
  },

  // ---------------------------------------------------------------------
  // LLM metadata
  // ---------------------------------------------------------------------
  llm: {
    description:
      "Loading-state placeholder. Use `shape=text` for paragraph rows (combine with `count` to stack multiple lines), `shape=circle` for avatar placeholders, `shape=rect` for card/image placeholders. Always resolve to real content once data arrives — skeletons are transient.",
    tags: ["loading", "placeholder", "shimmer"],
    examples: [
      {
        code: `UI.skeleton(shape="text", size="md", count=3)`,
        caption: "Three-line text placeholder.",
      },
      {
        code: `UI.skeleton(shape="circle", size="lg")`,
        caption: "Avatar placeholder.",
      },
    ],
    antiPatterns: [
      {
        code: `UI.column([UI.skeleton(shape="text")])   # never replaced with real content`,
        reason:
          "Skeletons are loading states. Leaving one in place permanently confuses users; gate it on `is_loading` and swap in the real content when ready.",
      },
    ],
    budget: { children: 0, siblings: 20, depth: 6 },
  },

  // ---------------------------------------------------------------------
  // Renderer mapping
  // ---------------------------------------------------------------------
  renderer: {
    react: "./renderers/react/FluxSkeleton.tsx",
    fallback: {
      component: "Text",
      map: {},
      notes:
        "Basic renderers have no shimmer primitive; the node degrades to an empty Text run. Users will see nothing — plan accordingly.",
    },
  },
});

/**
 * FluxProgress — determinate / indeterminate progress indicator.
 *
 * Extends `Slider` (the closest interactive basic-catalog shape with a
 * value axis), which forces `accessibility.label: "required"` via the
 * DSL invariant. Despite that lineage, progress is non-interactive: no
 * keyboard bindings; the renderer must set `role="progressbar"` and the
 * appropriate `aria-valuenow` / `aria-valuemin` / `aria-valuemax` so
 * screen readers announce it as a progress indicator rather than a
 * control.
 */

import { defineComponent, z } from "../dsl/types";

export default defineComponent({
  name: "FluxProgress",
  extends: "Slider",
  category: "primitive",

  // ---------------------------------------------------------------------
  // Schema
  // ---------------------------------------------------------------------
  schema: z.object({
    component: z.literal("FluxProgress"),
    id: z.string(),

    // Content
    value: z.number().min(0).max(100).default(0),
    label: z.string().optional(),

    // Behavior
    determinate: z.boolean().default(true),

    // Variant dimensions
    tone: z
      .enum(["default", "success", "warning", "danger"])
      .default("default"),
    size: z.enum(["sm", "md", "lg"]).default("md"),

    // Accessibility (required by DSL invariant).
    accessibility: z.object({
      label: z.string(),
      description: z.string().optional(),
    }),
  }),

  // ---------------------------------------------------------------------
  // Tokens referenced
  // ---------------------------------------------------------------------
  tokens: [
    "color.bg.subtle",
    "color.primary.solid",
    "color.success.solid",
    "color.warning.7",
    "color.danger.solid",
    "space.1",
    "space.1_5",
    "space.2",
    "radius.full",
    "motion.duration.slow",
    "motion.easing.emphasized",
  ],

  // ---------------------------------------------------------------------
  // Variant recipe (tone x size)
  // ---------------------------------------------------------------------
  variants: {
    tone: {
      default: {
        backgroundColor: "$color.bg.subtle",
        fillColor: "$color.primary.solid",
      },
      success: {
        backgroundColor: "$color.bg.subtle",
        fillColor: "$color.success.solid",
      },
      warning: {
        backgroundColor: "$color.bg.subtle",
        fillColor: "$color.warning.7",
      },
      danger: {
        backgroundColor: "$color.bg.subtle",
        fillColor: "$color.danger.solid",
      },
    },
    size: {
      sm: {
        height: "$space.1",
        borderRadius: "$radius.full",
      },
      md: {
        height: "$space.1_5",
        borderRadius: "$radius.full",
      },
      lg: {
        height: "$space.2",
        borderRadius: "$radius.full",
      },
    },
  },

  // ---------------------------------------------------------------------
  // compoundVariants — indeterminate default tone wires shimmer motion.
  // ---------------------------------------------------------------------
  compoundVariants: [
    {
      tone: "default",
      style: {
        transitionDuration: "$motion.duration.slow",
        transitionTimingFunction: "$motion.easing.emphasized",
      },
    },
  ],

  defaultVariants: {
    tone: "default",
    size: "md",
  },

  // ---------------------------------------------------------------------
  // Accessibility
  // ---------------------------------------------------------------------
  accessibility: {
    label: "required",
    role: "progressbar",
  },

  // ---------------------------------------------------------------------
  // LLM metadata
  // ---------------------------------------------------------------------
  llm: {
    description:
      "A progress indicator. Set `determinate=True` with a `value` in 0..100 when you know the ratio; set `determinate=False` for unknown-duration waits (the renderer animates a shimmer). Always provide `accessibility.label` — assistive tech needs context ('Uploading photo', not just 'progress').",
    tags: ["progress", "loading", "indicator"],
    examples: [
      {
        code: `UI.progress(value=60, label="Uploading", tone="default")`,
        caption: "Determinate progress at 60%.",
      },
      {
        code: `UI.progress(determinate=False, label="Preparing report", tone="default")`,
        caption: "Indeterminate shimmer for unknown-duration waits.",
      },
    ],
    antiPatterns: [
      {
        code: `UI.progress(value=40)   # no accessibility.label`,
        reason:
          "accessibility.label is required. Screen readers announce progress without any cue of what's progressing.",
      },
      {
        code: `UI.progress(value=150)`,
        reason:
          "value must be in 0..100. Pass determinate=False for unknown-bounded progress.",
      },
    ],
    budget: { children: 0, siblings: 4, depth: 6 },
  },

  // ---------------------------------------------------------------------
  // Renderer mapping
  // ---------------------------------------------------------------------
  renderer: {
    react: "./renderers/react/FluxProgress.tsx",
    fallback: {
      component: "Slider",
      map: {
        value: "value",
      },
      notes:
        "Basic renderers speak Slider — indeterminate mode and tone coloring are lost; the bar renders as a static slider pinned to `value`.",
    },
  },
});

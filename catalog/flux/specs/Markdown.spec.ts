/**
 * FluxMarkdown — rendered Markdown text block.
 *
 * The renderer escape hatch. Authors can write rich prose, headings,
 * lists, emphasis, links, and inline code; the renderer parses the
 * `source` string into a sanitised DOM subtree. Basic renderers that
 * don't speak flux degrade to `Text` with the raw markdown source — the
 * fallback contract documented below.
 *
 * Intentionally no compound variants: size and proseStyle are
 * orthogonal and the cross product has natural CSS behavior.
 */

import { defineComponent, z } from "../dsl/types";

export default defineComponent({
  name: "FluxMarkdown",
  extends: "Text",
  category: "primitive",

  // ---------------------------------------------------------------------
  // Schema
  // ---------------------------------------------------------------------
  schema: z.object({
    component: z.literal("FluxMarkdown"),
    id: z.string(),

    // Content
    source: z.string(),

    // Variant dimensions
    size: z.enum(["sm", "md", "lg"]).default("md"),
    proseStyle: z
      .enum(["compact", "default", "spacious"])
      .default("default"),

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
    "color.text.primary",
    "space.2",
    "space.3",
    "space.4",
    "typography.size.sm",
    "typography.size.md",
    "typography.size.lg",
    "typography.family.sans",
    "typography.lineHeight.normal",
    "typography.lineHeight.relaxed",
  ],

  // ---------------------------------------------------------------------
  // Variant recipe (size x proseStyle — no compounds)
  // ---------------------------------------------------------------------
  variants: {
    size: {
      sm: {
        fontSize: "$typography.size.sm",
        fontFamily: "$typography.family.sans",
        color: "$color.text.primary",
      },
      md: {
        fontSize: "$typography.size.md",
        fontFamily: "$typography.family.sans",
        color: "$color.text.primary",
      },
      lg: {
        fontSize: "$typography.size.lg",
        fontFamily: "$typography.family.sans",
        color: "$color.text.primary",
      },
    },
    proseStyle: {
      compact: {
        lineHeight: "$typography.lineHeight.normal",
        paragraphSpacing: "$space.2",
        headingSpacing: "$space.3",
      },
      default: {
        lineHeight: "$typography.lineHeight.normal",
        paragraphSpacing: "$space.3",
        headingSpacing: "$space.4",
      },
      spacious: {
        lineHeight: "$typography.lineHeight.relaxed",
        paragraphSpacing: "$space.4",
        headingSpacing: "$space.4",
      },
    },
  },

  defaultVariants: {
    size: "md",
    proseStyle: "default",
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
      "Renders a Markdown source string as a prose block. The renderer sanitises HTML. Use `proseStyle=compact` for dense copy (tooltips, help), `default` for body text, `spacious` for long-form articles. Reach for plain `UI.text` for one-line labels — Markdown is overhead you don't need.",
    tags: ["text", "prose", "markdown", "escape-hatch"],
    examples: [
      {
        code: `UI.markdown("**Tip:** press Cmd+K to open the quick-switcher.")`,
        caption: "Short inline help with bold + code formatting.",
      },
      {
        code: `UI.markdown(help_article, proseStyle="spacious", size="md")`,
        caption: "Full documentation snippet rendered spaciously.",
      },
    ],
    antiPatterns: [
      {
        code: `UI.markdown("<script>alert('xss')</script>")`,
        reason:
          "Raw HTML (especially scripts) must be stripped by the renderer. Don't rely on Markdown to pass HTML through; it won't.",
      },
      {
        code: `UI.markdown("Email")   # one-line label`,
        reason:
          "Use UI.text for single-word labels. Markdown adds a parsing step with no payoff.",
      },
    ],
    budget: { children: 0, siblings: 6, depth: 6 },
  },

  // ---------------------------------------------------------------------
  // Renderer mapping
  // ---------------------------------------------------------------------
  renderer: {
    react: "./renderers/react/FluxMarkdown.tsx",
    fallback: {
      component: "Text",
      map: {
        source: "text",
      },
      notes:
        "Basic renderers lose markdown formatting; raw source is shown as plain text.",
    },
  },
});

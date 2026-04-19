# Authoring a flux component — 5-minute tour

flux components are single `.spec.ts` files. One file, one component,
one default export. The build picks them up, validates, and emits
everything downstream.

## 1. Minimum viable spec

```ts
import { defineComponent, z } from "../dsl/types";

export default defineComponent({
  name: "FluxBadge",
  extends: "Text",
  category: "primitive",
  schema: z.object({
    component: z.literal("FluxBadge"),
    id:        z.string(),
    label:     z.string(),
    tone:      z.enum(["neutral", "brand", "success", "danger"]).default("neutral"),
  }),
  tokens: [
    "color.bg.subtle",
    "color.text.primary",
    "color.success.solid",
    "color.danger.solid",
    "radius.sm",
    "space.1",
    "space.2",
    "typography.size.xs",
  ],
  variants: {
    tone: {
      neutral: { background: "$color.bg.subtle",      color: "$color.text.primary" },
      brand:   { background: "$color.primary.subtle", color: "$color.text.primary" },
      success: { background: "$color.success.solid",  color: "$color.text.onBrand" },
      danger:  { background: "$color.danger.solid",   color: "$color.text.onBrand" },
    },
  },
  defaultVariants: { tone: "neutral" },
  accessibility: { label: "optional", role: "status" },
  llm: {
    description: "Compact label for status, counts, or tags. Not clickable.",
    examples: [
      { code: `UI.badge("New", tone="brand")`, caption: "Brand-toned tag" },
      { code: `UI.badge("Live", tone="success")`, caption: "Live status" },
    ],
    antiPatterns: [
      { code: `UI.badge("Click me", action=...)`, reason: "Badges are not interactive. Use UI.button." },
    ],
    budget: { children: 0, siblings: 12 },
  },
  renderer: {
    react: "./renderers/react/FluxBadge.tsx",
    fallback: { component: "Text", map: { label: "text" } },
  },
});
```

## 2. Rules of the road

- Name MUST start with `Flux`.
- Every interactive component (extends one of `Button`, `TextField`, `CheckBox`, `ChoicePicker`, `Slider`, `DateTimeInput`) MUST set `accessibility.label: "required"`.
- Every style value in `variants` / `compoundVariants` MUST be either a `$token.path` or a raw literal — the build will fail if a token path is missing from the active pack.
- `llm.examples` must have at least one entry. Use two good ones plus two anti-patterns if the component has footguns.
- `schema` is Zod. Always include `component: z.literal("FluxX")` and `id: z.string()`.

## 3. Runtime hooks

Never write CSS by hand. Write tokens; the codegen turns them into CSS vars. Never write a React component by hand until the scaffold exists — run `just flux` first, then edit `ts/src/flux/renderer/FluxX.tsx`.

## 4. Gotchas

- `extends` determines the **fallback** component used by basic-only renderers. Pick the closest-shape basic component.
- Slots reference children by A2UI component id, not inline. The codegen wires slot keys to `ComponentId` references in the emitted JSON schema.
- Avoid adding a variant dimension with fewer than 2 values — just inline the style.

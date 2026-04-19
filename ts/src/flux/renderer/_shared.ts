// flux:scaffold-user
/**
 * Shared utilities for flux renderers.
 *
 * Each renderer imports from here to keep variant-driven style composition
 * consistent and to funnel the React-element → FluxElement cast through a
 * single audited location.
 */

import * as React from "react";
import type { CSSProperties, ReactElement, ReactNode } from "react";
import type { FluxElement, FluxNode, FluxRenderContext, FluxRenderer } from "./types.js";

/**
 * Cast a React element to the structural FluxElement interface. The
 * generated types intentionally keep FluxElement react-agnostic; this
 * shim is the single boundary where we accept the narrowing.
 */
export function asFluxElement(element: ReactElement): FluxElement {
  return element as unknown as FluxElement;
}

/** Shorthand for ``React.createElement`` with a narrowed FluxElement return. */
export function h(
  type: string | React.ComponentType<Record<string, unknown>>,
  props: Record<string, unknown> | null,
  ...children: ReactNode[]
): ReactElement {
  return React.createElement(
    type as unknown as React.ElementType,
    (props ?? undefined) as React.Attributes,
    ...children,
  );
}

/**
 * Build a CSS variable reference string.
 *
 *   tokenVar("color.primary.solid") → "var(--flux-color-primary-solid)"
 */
export function tokenVar(path: string, fallback?: string): string {
  const varName = `--flux-${path.split(".").map(kebab).join("-")}`;
  return fallback ? `var(${varName}, ${fallback})` : `var(${varName})`;
}

function kebab(segment: string): string {
  return segment.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();
}

/**
 * Resolve a single value from the flux catalog's variant style shape. If
 * the value starts with ``$``, convert to a ``var(--flux-…)`` reference;
 * otherwise pass through untouched.
 */
export function resolveValue(value: unknown): unknown {
  if (typeof value === "string" && value.startsWith("$")) {
    return tokenVar(value.slice(1));
  }
  return value;
}

/**
 * Convert an object of token-referencing style properties to a runtime
 * CSSProperties object. Also converts camelCase CSS props to the shape
 * React expects (React already uses camelCase — so this is largely a
 * token-resolution pass with type narrowing).
 */
export function resolveStyle(style: Record<string, unknown> | undefined): CSSProperties {
  const out: Record<string, unknown> = {};
  if (!style) return out as CSSProperties;
  for (const [key, value] of Object.entries(style)) {
    out[key] = resolveValue(value);
  }
  return out as CSSProperties;
}

/**
 * Merge an ordered list of style dicts. Later entries win. Undefined
 * values are treated as "don't set".
 */
export function mergeStyles(...styles: Array<CSSProperties | undefined>): CSSProperties {
  const out: Record<string, unknown> = {};
  for (const block of styles) {
    if (!block) continue;
    for (const [key, value] of Object.entries(block)) {
      if (value !== undefined) out[key] = value;
    }
  }
  return out as CSSProperties;
}

/** Look up a slot node (by id) via ctx.renderers. */
export function renderSlot(
  slotId: unknown,
  ctx: FluxRenderContext,
  parentId: string,
  slotName: string,
): ReactElement | null {
  if (typeof slotId !== "string" || slotId.length === 0) return null;
  // Surface-level lookup not modelled in ctx — the visual runner passes a
  // ``__slots`` sidecar via ctx.renderers' closure. The fixture runner
  // attaches a ``FLUX_SLOT_REGISTRY`` map on ctx with slot nodes keyed by id.
  const registry = (ctx as unknown as { slots?: Record<string, FluxNode> }).slots;
  if (!registry) return null;
  const child = registry[slotId];
  if (!child) return null;
  const renderer = ctx.renderers[child.component] as FluxRenderer | undefined;
  const rendered = renderer ? renderer(child, ctx) : ctx.fallback(child);
  return React.cloneElement(rendered as unknown as ReactElement, {
    key: `${parentId}-${slotName}`,
  });
}

/** Return the first non-nullish value. */
export function firstDefined<T>(...values: Array<T | undefined | null>): T | undefined {
  for (const v of values) {
    if (v !== undefined && v !== null) return v;
  }
  return undefined;
}

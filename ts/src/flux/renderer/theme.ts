// flux:scaffold-user
/**
 * Flux theme adapter.
 *
 * Walks a JSON token pack (``catalog/flux/tokens/flux-light.json`` etc.)
 * and flattens it into CSS custom properties under the ``--flux-`` prefix.
 *
 * Key conventions:
 *   - Dotted paths become ``-``-joined segments.
 *   - Underscores become ``_`` (e.g. ``space.0_5`` → ``--flux-space-0_5``).
 *     Underscore preservation matches the token file keys; renderer CSS
 *     uses the same keys.
 *   - ``$meta`` entries are skipped.
 *   - Number values are emitted as raw numbers (useful for font-weight,
 *     line-height, z-index).
 *
 * Exports:
 *   - ``renderTokenPack(pack)`` — produces a CSS string.
 *   - ``useTheme(packId, pack)`` — React hook that injects a ``<style>``
 *     tag scoped by ``[data-flux-theme="<id>"]``.
 *   - ``FluxThemeRoot`` — convenience wrapper component.
 */

import * as React from "react";

export type TokenPack = Record<string, unknown>;

const PREFIX = "--flux";

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function kebabCase(segment: string): string {
  // Preserve underscore suffixes (e.g. "0_5") — they're part of the token
  // identifier. Lowercase everything else; insert a dash before any
  // interior uppercase letter.
  return segment.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();
}

function flatten(pack: TokenPack, prefix: string, out: Array<[string, string]>): void {
  for (const [rawKey, value] of Object.entries(pack)) {
    if (rawKey.startsWith("$")) continue;
    const key = kebabCase(rawKey);
    const path = prefix ? `${prefix}-${key}` : key;
    if (isPlainObject(value)) {
      flatten(value, path, out);
      continue;
    }
    if (value === null || value === undefined) continue;
    if (typeof value === "number") {
      out.push([`${PREFIX}-${path}`, String(value)]);
      continue;
    }
    if (typeof value === "string") {
      out.push([`${PREFIX}-${path}`, value]);
      continue;
    }
    // Arrays / booleans flatten to JSON — rare in token packs but safe.
    out.push([`${PREFIX}-${path}`, JSON.stringify(value)]);
  }
}

/**
 * Render a token pack to a CSS string scoped by
 * ``[data-flux-theme="<packId>"]``. The caller is responsible for injecting
 * the resulting CSS into the page (e.g. via ``useTheme`` or a build-time
 * plugin).
 */
export function renderTokenPack(pack: TokenPack, packId?: string): string {
  const decls: Array<[string, string]> = [];
  flatten(pack, "", decls);
  const body = decls.map(([name, value]) => `  ${name}: ${value};`).join("\n");
  const selector = packId ? `[data-flux-theme="${packId}"]` : ":root";
  return `${selector} {\n${body}\n}\n`;
}

const injectedThemes = new Map<string, { css: string; refs: number; element: HTMLStyleElement }>();

/**
 * Inject a token pack's CSS into the document ``<head>`` for the duration
 * of the component's lifetime. Ref-counted — multiple consumers of the
 * same ``packId`` share a single ``<style>`` block.
 */
export function useTheme(packId: string, pack: TokenPack): void {
  React.useEffect(() => {
    if (typeof document === "undefined") return undefined;
    const existing = injectedThemes.get(packId);
    if (existing) {
      existing.refs += 1;
    } else {
      const element = document.createElement("style");
      element.setAttribute("data-flux-theme-pack", packId);
      element.textContent = renderTokenPack(pack, packId);
      document.head.appendChild(element);
      injectedThemes.set(packId, { css: element.textContent, refs: 1, element });
    }
    return () => {
      const entry = injectedThemes.get(packId);
      if (!entry) return;
      entry.refs -= 1;
      if (entry.refs <= 0) {
        entry.element.remove();
        injectedThemes.delete(packId);
      }
    };
  }, [packId, pack]);
}

export interface FluxThemeRootProps {
  packId: string;
  pack: TokenPack;
  className?: string;
  children?: React.ReactNode;
}

/**
 * Wraps its children in a ``<div data-flux-theme="<packId>">`` and injects
 * the pack's CSS custom properties at mount. Use once near the root of a
 * surface tree.
 */
export function FluxThemeRoot(props: FluxThemeRootProps): React.ReactElement {
  const { packId, pack, className, children } = props;
  useTheme(packId, pack);
  return React.createElement(
    "div",
    {
      "data-flux-theme": packId,
      className,
      style: {
        fontFamily: "var(--flux-typography-family-sans)",
        color: "var(--flux-color-text-primary)",
        backgroundColor: "var(--flux-color-bg-canvas)",
        minHeight: "100%",
      },
    },
    children,
  );
}

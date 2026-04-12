/**
 * Web tools — `web_fetch` and `web_search` using global `fetch`.
 *
 * Mirrors `_harness/_web.py`. The Python harness reuses ADK's
 * `UrlContextTool`/`GoogleSearchTool` when available; the TS version
 * uses Node 20+'s built-in `fetch` and skips the search provider stub
 * (callers should pass their own `searchProvider`).
 */

import { type SandboxPolicy } from "./sandbox.js";
import { asTool, type HarnessTool } from "./types.js";

export interface WebOptions {
  search?: boolean;
  searchProvider?: HarnessTool | null;
  maxBytes?: number;
  timeoutMs?: number;
}

export function webTools(sandbox: SandboxPolicy, opts: WebOptions = {}): HarnessTool[] {
  if (!sandbox.allowNetwork) return [];
  const maxBytes = opts.maxBytes ?? 100_000;
  const timeoutMs = opts.timeoutMs ?? 30_000;
  const tools: HarnessTool[] = [];

  tools.push(
    asTool("web_fetch", async (args: { url: string; method?: string }) => {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), timeoutMs);
      try {
        const res = await fetch(args.url, {
          method: args.method ?? "GET",
          signal: ctrl.signal,
        });
        const text = await res.text();
        const truncated = text.length > maxBytes;
        return {
          status: res.status,
          url: res.url,
          contentType: res.headers.get("content-type") ?? "",
          body: truncated ? text.slice(0, maxBytes) : text,
          truncated,
        };
      } finally {
        clearTimeout(timer);
      }
    }),
  );

  if (opts.search ?? true) {
    if (opts.searchProvider) {
      tools.push(opts.searchProvider);
    } else {
      tools.push(
        asTool("web_search", async (_args: { query: string }) => {
          // Stub: callers should provide a real provider via opts.searchProvider.
          return {
            results: [],
            note: "No search provider configured. Pass `searchProvider` to H.web().",
          };
        }),
      );
    }
  }

  return tools;
}

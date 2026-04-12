/**
 * Event renderers — pure functions that convert HarnessEvents to display
 * strings. Renderers do NOT touch I/O; the caller decides where to write.
 *
 * Mirrors `_harness/_renderer.py`.
 */

import type { HarnessEvent } from "./events.js";

export interface RendererOptions {
  showTiming?: boolean;
  showArgs?: boolean;
  verbose?: boolean;
}

export interface Renderer {
  render(event: HarnessEvent): string | null;
}

/** Plain-text renderer — single-line per event. */
export class PlainRenderer implements Renderer {
  readonly showTiming: boolean;
  readonly showArgs: boolean;
  readonly verbose: boolean;

  constructor(opts: RendererOptions = {}) {
    this.showTiming = opts.showTiming ?? true;
    this.showArgs = opts.showArgs ?? false;
    this.verbose = opts.verbose ?? false;
  }

  render(event: HarnessEvent): string | null {
    switch (event.kind) {
      case "text":
        return event.text;
      case "tool_call_start": {
        const args = this.showArgs && event.args ? ` ${JSON.stringify(event.args)}` : "";
        return `▸ ${event.toolName}${args}`;
      }
      case "tool_call_end": {
        const dur = this.showTiming && event.durationMs != null ? ` (${event.durationMs}ms)` : "";
        return `✓ ${event.toolName}${dur}`;
      }
      case "tool_call_error":
        return `✗ ${event.toolName}: ${event.error ?? "error"}`;
      case "compression":
        return `⌬ context compressed`;
      case "interrupt":
        return `⏸ interrupted`;
      case "error":
        return `! error: ${(event as { data?: { message?: string } }).data?.message ?? "unknown"}`;
      default:
        return this.verbose ? `[${event.kind}]` : null;
    }
  }
}

/** Rich renderer — same as plain but with ANSI colors. */
export class RichRenderer extends PlainRenderer {
  override render(event: HarnessEvent): string | null {
    const base = super.render(event);
    if (!base) return null;
    if (event.kind === "tool_call_error") return `\u001b[31m${base}\u001b[0m`;
    if (event.kind === "tool_call_end") return `\u001b[32m${base}\u001b[0m`;
    if (event.kind === "tool_call_start") return `\u001b[36m${base}\u001b[0m`;
    return base;
  }
}

/** JSON renderer — one JSON object per event. */
export class JsonRenderer implements Renderer {
  render(event: HarnessEvent): string {
    return JSON.stringify(event);
  }
}

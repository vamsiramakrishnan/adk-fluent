/**
 * Minimal interactive REPL for a harness agent. Uses node:readline.
 *
 * Mirrors `_harness/_repl.py` but pares the interactive surface down to
 * the parts that translate cleanly: prompt → run agent → render events →
 * loop. Slash commands are handled by `CommandRegistry`. The Python
 * implementation has rich live-rendering and prompt_toolkit hooks; the
 * TS port keeps it intentionally simple so it works in any terminal.
 */

import * as readline from "node:readline/promises";
import { stdin, stdout } from "node:process";
import type { CommandRegistry } from "./registries.js";
import type { ContextCompressor } from "./lifecycle.js";
import type { EventDispatcher, HarnessEvent } from "./events.js";
import type { HookRegistry } from "./registries.js";
import { PlainRenderer, type Renderer } from "./renderer.js";

export interface ReplConfig {
  prompt?: string;
  exitWords?: string[];
  renderer?: Renderer;
}

/**
 * A harness REPL drives an agent through a stdin/stdout loop. The
 * `agent` parameter is intentionally typed as `unknown` so consumers
 * can pass any object that implements `ask(text: string)` — this
 * keeps the REPL decoupled from the @google/adk runtime.
 */
export class HarnessRepl {
  readonly agent: { ask?: (text: string) => Promise<string> };
  readonly dispatcher?: EventDispatcher;
  readonly hooks?: HookRegistry;
  readonly compressor?: ContextCompressor;
  readonly config: Required<ReplConfig>;

  constructor(
    agent: { ask?: (text: string) => Promise<string> },
    opts: {
      dispatcher?: EventDispatcher;
      hooks?: HookRegistry;
      compressor?: ContextCompressor;
      config?: ReplConfig;
    } = {},
  ) {
    this.agent = agent;
    this.dispatcher = opts.dispatcher;
    this.hooks = opts.hooks;
    this.compressor = opts.compressor;
    this.config = {
      prompt: opts.config?.prompt ?? "> ",
      exitWords: opts.config?.exitWords ?? ["exit", "quit", ":q"],
      renderer: opts.config?.renderer ?? new PlainRenderer(),
    };
  }

  /** Run the REPL loop until the user exits. */
  async run(commands?: CommandRegistry): Promise<void> {
    const rl = readline.createInterface({ input: stdin, output: stdout });
    try {
      while (true) {
        const line = (await rl.question(this.config.prompt)).trim();
        if (!line) continue;
        if (this.config.exitWords.includes(line)) break;

        if (commands?.isCommand(line)) {
          const out = await commands.dispatch(line);
          if (out) stdout.write(out + "\n");
          continue;
        }

        await this.hooks?.fire("turn_start", { input: line });
        try {
          const reply = (await this.agent.ask?.(line)) ?? "";
          stdout.write(reply + "\n");
        } catch (err) {
          stdout.write(`! error: ${(err as Error).message}\n`);
          await this.hooks?.fire("error", { error: (err as Error).message });
        }
        await this.hooks?.fire("turn_complete", { input: line });
      }
    } finally {
      rl.close();
    }
  }

  /** Render a single event through the configured renderer. */
  render(event: HarnessEvent): void {
    const out = this.config.renderer.render(event);
    if (out) stdout.write(out + "\n");
  }
}

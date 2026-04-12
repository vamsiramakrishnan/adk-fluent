/**
 * A2A (Agent-to-Agent) — remote agent communication.
 *
 * Mirrors Python's `RemoteAgent`, `A2AServer`, and `AgentRegistry`. The TS
 * port is interface-only at this stage: it produces tagged config objects
 * that a future runtime layer (or `.native()` hook) can wire to a real
 * A2A transport. The fluent surface is identical to the Python version.
 */

import { BuilderBase, autoBuild } from "../core/builder-base.js";

/**
 * Consume a remote A2A agent. Behaves like a regular builder so it can be
 * used inside Pipeline / FanOut / Loop / Fallback chains.
 *
 *   const remote = new RemoteAgent("researcher", {
 *     agentCard: "http://researcher:8001/.well-known/agent.json",
 *   })
 *     .describe("Remote research specialist")
 *     .timeout(30)
 *     .sends("query")
 *     .receives("findings")
 *     .persistentContext();
 */
export interface RemoteAgentOptions {
  agentCard?: string;
  env?: string;
}

export class RemoteAgent extends BuilderBase<Record<string, unknown>> {
  constructor(name: string, opts: RemoteAgentOptions = {}) {
    super(name);
    if (opts.agentCard !== undefined) {
      this._config.set("agent_card", opts.agentCard);
    }
    if (opts.env !== undefined) {
      this._config.set("env", opts.env);
    }
  }

  describe(text: string): this {
    return this._setConfig("description", text);
  }

  timeout(seconds: number): this {
    return this._setConfig("timeout", seconds);
  }

  /** State keys to serialize into the outgoing A2A message. */
  sends(...keys: string[]): this {
    return this._setConfig("_sends", keys);
  }

  /** State keys to deserialize from the A2A response. */
  receives(...keys: string[]): this {
    return this._setConfig("_receives", keys);
  }

  /** Maintain ``contextId`` across calls in the same session. */
  persistentContext(enabled = true): this {
    return this._setConfig("_persistent_context", enabled);
  }

  build(): Record<string, unknown> {
    return this._buildConfig("RemoteAgent");
  }

  /** Discover a remote agent via DNS-based ``.well-known`` lookup. */
  static discover(host: string, name?: string): RemoteAgent {
    const agent = new RemoteAgent(name ?? host, {
      agentCard: `https://${host}/.well-known/agent.json`,
    });
    return agent;
  }
}

/**
 * Publish a local agent via the A2A protocol.
 *
 *   const server = new A2AServer(myAgent)
 *     .port(8001)
 *     .version("1.0.0")
 *     .provider("Acme Corp", "https://acme.com")
 *     .skill("research", "Academic Research", { tags: ["citations"] })
 *     .healthCheck()
 *     .gracefulShutdown(30);
 */
export class A2AServer extends BuilderBase<Record<string, unknown>> {
  private _agent: BuilderBase | unknown;
  private _skills: Array<Record<string, unknown>> = [];
  private _provider: { name: string; url?: string } | null = null;

  constructor(agent: BuilderBase | unknown, name?: string) {
    super(name ?? "a2a_server");
    this._agent = agent;
  }

  protected override _clone(): this {
    const clone = super._clone();
    (clone as A2AServer)._agent = this._agent;
    (clone as A2AServer)._skills = [...this._skills];
    (clone as A2AServer)._provider = this._provider
      ? { ...this._provider }
      : null;
    return clone;
  }

  port(p: number): this {
    return this._setConfig("port", p);
  }

  version(v: string): this {
    return this._setConfig("version", v);
  }

  provider(name: string, url?: string): this {
    const clone = this._clone();
    clone._provider = { name, url };
    return clone;
  }

  skill(
    id: string,
    title: string,
    opts: { description?: string; tags?: string[] } = {},
  ): this {
    const clone = this._clone();
    clone._skills.push({ id, title, ...opts });
    return clone;
  }

  healthCheck(enabled = true): this {
    return this._setConfig("_health_check", enabled);
  }

  gracefulShutdown(timeoutSeconds = 30): this {
    return this._setConfig("_graceful_shutdown_timeout", timeoutSeconds);
  }

  build(): Record<string, unknown> {
    return {
      _type: "A2AServer",
      name: this._config.get("name"),
      agent: this._agent instanceof BuilderBase ? autoBuild(this._agent) : this._agent,
      port: this._config.get("port"),
      version: this._config.get("version"),
      provider: this._provider,
      skills: this._skills,
      healthCheck: this._config.get("_health_check") ?? false,
      gracefulShutdownTimeout: this._config.get("_graceful_shutdown_timeout"),
    };
  }
}

/**
 * Registry-based discovery of remote agents.
 *
 *   const registry = new AgentRegistry("http://registry:9000");
 *   const remote = await registry.find({ name: "researcher" });
 */
export class AgentRegistry {
  constructor(public readonly url: string) {}

  /**
   * Look up a remote agent by name. Returns a stub ``RemoteAgent``
   * pre-configured with the registry-provided agent-card URL.
   *
   * The runtime layer is responsible for actually contacting the registry
   * — this stub records the lookup metadata.
   */
  find(query: { name?: string; tags?: string[] } = {}): RemoteAgent {
    const remote = new RemoteAgent(query.name ?? "unknown", {
      agentCard: `${this.url}/agents/${query.name ?? ""}`,
    });
    return remote;
  }
}

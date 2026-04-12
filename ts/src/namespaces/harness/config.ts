/**
 * Unified harness configuration. Mirrors `_harness/_config.py`.
 *
 * `HarnessConfig` is a pure-data bag that aggregates the building
 * blocks created by the various `H.*` factories. It does NOT execute
 * anything — it's the value passed to `Agent.harness(...)`.
 */

import type { ApprovalMemory, PermissionPolicy } from "./permissions.js";
import type { SandboxPolicy } from "./sandbox.js";
import type { ErrorStrategy } from "./error-strategy.js";
import type { UsageTracker } from "./usage.js";
import type { ProjectMemory } from "./memory.js";

export interface HarnessConfigOptions {
  permissions?: PermissionPolicy;
  sandbox?: SandboxPolicy;
  autoCompressThreshold?: number;
  approvalHandler?: (toolName: string, args: Record<string, unknown>) => boolean | Promise<boolean>;
  approvalMemory?: ApprovalMemory;
  usage?: UsageTracker;
  memory?: ProjectMemory;
  onError?: ErrorStrategy;
}

export class HarnessConfig {
  readonly permissions?: PermissionPolicy;
  readonly sandbox?: SandboxPolicy;
  readonly autoCompressThreshold: number;
  readonly approvalHandler?: HarnessConfigOptions["approvalHandler"];
  readonly approvalMemory?: ApprovalMemory;
  readonly usage?: UsageTracker;
  readonly memory?: ProjectMemory;
  readonly onError?: ErrorStrategy;

  constructor(opts: HarnessConfigOptions = {}) {
    this.permissions = opts.permissions;
    this.sandbox = opts.sandbox;
    this.autoCompressThreshold = opts.autoCompressThreshold ?? 100_000;
    this.approvalHandler = opts.approvalHandler;
    this.approvalMemory = opts.approvalMemory;
    this.usage = opts.usage;
    this.memory = opts.memory;
    this.onError = opts.onError;
  }
}

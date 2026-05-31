/**
 * HITL approval UX (Capability #8) — TS parity tests.
 *
 * Mirrors python/tests covering `_permissions/_interactive.py`. Drives the
 * `InteractiveApprovalHandler` along the plugin's ask-path: a policy that
 * ASKs for "bash" produces a `PermissionDecision.ask`, the handler renders a
 * `UI.confirm` surface, delegates to an injected fake responder (no stdin),
 * and resolves allow/deny. An ALWAYS verdict records into `ApprovalMemory` so
 * the second ask short-circuits without calling the responder.
 */

import { describe, expect, it } from "vitest";

import {
  ApprovalMemory,
  ApprovalRequest,
  ApprovalVerdict,
  InteractiveApprovalHandler,
  PermissionDecision,
  PermissionPolicy,
  type Responder,
} from "../../src/namespaces/harness/permissions.js";
import { UI } from "../../src/namespaces/ui.js";

/** Resolve a permission decision for `bash` via the policy's ask-path. */
function askDecision(toolName = "bash") {
  const policy = new PermissionPolicy({ ask: [toolName] });
  const decision = policy.check(toolName);
  expect(decision.isAsk).toBe(true);
  return decision;
}

describe("HITL approval / InteractiveApprovalHandler", () => {
  it("UI.approval returns an InteractiveApprovalHandler", () => {
    const handler = UI.approval({ responder: () => true });
    expect(handler).toBeInstanceOf(InteractiveApprovalHandler);
    expect(typeof handler.handler).toBe("function");
  });

  it("allows when the responder returns true", async () => {
    const decision = askDecision();
    const handler = UI.approval({ responder: () => true });
    const granted = await handler.handler("bash", { cmd: "ls" }, decision);
    expect(granted).toBe(true);
  });

  it("denies when the responder returns false", async () => {
    const decision = askDecision();
    const handler = UI.approval({ responder: () => false });
    const granted = await handler.handler("bash", { cmd: "rm -rf /" }, decision);
    expect(granted).toBe(false);
  });

  it("builds a confirm message that includes the tool name", async () => {
    let seen: ApprovalRequest | undefined;
    const responder: Responder = (req) => {
      seen = req;
      return false;
    };
    const handler = UI.approval({ responder });
    // No reason on the decision → handler synthesizes `Run \`bash\`(cmd=...)`.
    await handler.handler("bash", { cmd: "ls -la" }, PermissionDecision.ask());

    expect(seen).toBeInstanceOf(ApprovalRequest);
    expect(seen!.toolName).toBe("bash");
    // The synthesized prompt mentions the tool and its input.
    expect(seen!.prompt).toContain("bash");
    expect(seen!.prompt).toContain("cmd");
    // A confirm surface is compiled and carried on the request.
    expect(seen!.surface).toBeDefined();
    const flat = JSON.stringify(seen!.surface);
    expect(flat).toContain("bash");
  });

  it("prefers the decision's reason as the prompt when present", async () => {
    const policy = new PermissionPolicy({ ask: ["bash"] });
    const decision = policy.check("bash");
    let seen: ApprovalRequest | undefined;
    const handler = UI.approval({
      responder: (req) => {
        seen = req;
        return true;
      },
    });
    await handler.handler("bash", {}, decision);
    // policy.check sets reason "Policy asks about 'bash'."
    expect(seen!.prompt).toBe(decision.reason);
  });

  it("ALWAYS verdict records into ApprovalMemory and short-circuits the next ask", async () => {
    const memory = new ApprovalMemory();
    let calls = 0;
    const responder: Responder = () => {
      calls += 1;
      return ApprovalVerdict.ALWAYS;
    };
    const handler = UI.approval({ responder, memory });

    // First ask → responder fires, verdict ALWAYS, allowed, remembered.
    const first = await handler.handler("bash", { cmd: "ls" }, askDecision());
    expect(first).toBe(true);
    expect(calls).toBe(1);
    expect(memory.recall("bash")).toBe(true);

    // Second ask → short-circuits via memory; responder NOT called again.
    const second = await handler.handler("bash", { cmd: "pwd" }, askDecision());
    expect(second).toBe(true);
    expect(calls).toBe(1);
  });

  it("NEVER verdict records a deny that short-circuits the next ask", async () => {
    const memory = new ApprovalMemory();
    let calls = 0;
    const responder: Responder = () => {
      calls += 1;
      return ApprovalVerdict.NEVER;
    };
    const handler = UI.approval({ responder, memory });

    const first = await handler.handler("bash", {}, askDecision());
    expect(first).toBe(false);
    expect(memory.recall("bash")).toBe(false);

    const second = await handler.handler("bash", {}, askDecision());
    expect(second).toBe(false);
    expect(calls).toBe(1);
  });

  it("ALLOW / DENY one-shot verdicts are not remembered", async () => {
    const memory = new ApprovalMemory();
    const handler = UI.approval({
      responder: () => ApprovalVerdict.ALLOW,
      memory,
    });
    const granted = await handler.handler("bash", {}, askDecision());
    expect(granted).toBe(true);
    // One-shot ALLOW must not persist a tool-level verdict.
    expect(memory.recall("bash")).toBeNull();
  });

  it("supports async responders", async () => {
    const handler = UI.approval({
      responder: async () => {
        await Promise.resolve();
        return true;
      },
    });
    expect(await handler.handler("bash", {}, askDecision())).toBe(true);
  });

  it("throws on an unknown verdict string", async () => {
    const handler = UI.approval({ responder: () => "maybe" });
    await expect(handler.handler("bash", {}, askDecision())).rejects.toThrow(
      /unknown approval verdict/,
    );
  });

  it("a custom message builder overrides the rendered prompt", async () => {
    let seen: ApprovalRequest | undefined;
    const handler = UI.approval({
      message: (tool, input) => `APPROVE ${tool} :: ${Object.keys(input).join(",")}`,
      responder: (req) => {
        seen = req;
        return true;
      },
    });
    await handler.handler("bash", { cmd: "ls" }, askDecision());
    expect(seen!.prompt).toBe("APPROVE bash :: cmd");
  });
});

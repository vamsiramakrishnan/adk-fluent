/**
 * A.watch / A.watchVersion / A.onChange — artifact subscribe/observe (Capability #7).
 *
 * Mirrors the spec-structure test pattern used for the rest of the A namespace
 * (see namespaces-expanded.test.ts): A.* ops return AComposite descriptors whose
 * `.ops[].type` / `.ops[].config` carry the artifact bridge metadata that the JS
 * ADK build step consumes. These tests prove the descriptors reuse the existing
 * snapshot (artifact → state content) and version (content-free change signal) op
 * machinery, and that watch differs from snapshot only in intent (the `watch`
 * marker), not in runtime path.
 */

import { describe, it, expect } from "vitest";
import { A, AComposite } from "../../src/namespaces/artifacts.js";

describe("A.watch — load latest artifact content into state", () => {
  it("loads content via the snapshot op into the target state key", () => {
    const a = A.watch("inbox.json", { intoKey: "inbox" });
    expect(a).toBeInstanceOf(AComposite);
    // Reuses the snapshot op (artifact -> state content bridge).
    expect(a.ops[0].type).toBe("snapshot");
    expect(a.ops[0].config.filename).toBe("inbox.json");
    expect(a.ops[0].config.intoKey).toBe("inbox");
  });

  it("defaults intoKey from the filename stem (like snapshot)", () => {
    const a = A.watch("report.md");
    expect(a.ops[0].config.intoKey).toBe("report");
  });

  it("differs from snapshot in INTENT via the `watch` marker", () => {
    const watch = A.watch("data.json", { intoKey: "data" });
    const snapshot = A.snapshot("data.json", { intoKey: "data" });
    // Same runtime op...
    expect(watch.ops[0].type).toBe(snapshot.ops[0].type);
    // ...but watch flags itself as a re-runnable observation.
    expect(watch.ops[0].config.watch).toBe(true);
    expect(snapshot.ops[0].config.watch).toBeUndefined();
  });

  it("honors a pinned version and scope", () => {
    const a = A.watch("doc.pdf", { intoKey: "doc", version: 3, scope: "user" });
    expect(a.ops[0].config.version).toBe(3);
    expect(a.ops[0].config.scope).toBe("user");
  });

  it("composes with .pipe() like other A ops", () => {
    const composed = A.watch("inbox.json", { intoKey: "inbox" }).pipe(
      A.watchVersion("inbox.json", { into: "inbox_version" }),
    );
    expect(composed.ops.length).toBe(2);
    expect(composed.ops[0].type).toBe("snapshot");
    expect(composed.ops[1].type).toBe("version");
  });
});

describe("A.watchVersion — record version metadata as a change signal", () => {
  it("records version metadata via the content-free version op", () => {
    const a = A.watchVersion("inbox.json", { into: "inbox_version" });
    expect(a).toBeInstanceOf(AComposite);
    // Reuses the version op (cheap, content-free metadata read).
    expect(a.ops[0].type).toBe("version");
    expect(a.ops[0].config.filename).toBe("inbox.json");
    expect(a.ops[0].config.intoKey).toBe("inbox_version");
    expect(a.ops[0].config.watch).toBe(true);
  });

  it("defaults the into key from the filename", () => {
    const a = A.watchVersion("inbox.json");
    expect(a.ops[0].config.intoKey).toBe("inbox.json_version");
  });

  it("is content-free relative to watch (no content load, just the signal)", () => {
    const ver = A.watchVersion("inbox.json", { into: "v" });
    const content = A.watch("inbox.json", { intoKey: "c" });
    expect(ver.ops[0].type).toBe("version"); // change trigger
    expect(content.ops[0].type).toBe("snapshot"); // content load
  });
});

describe("A.onChange — version signal + content load + handler", () => {
  it("returns [watchVersionStep, watchStep, handler] mirroring the Python tuple", () => {
    const handler = { name: "processor" };
    const steps = A.onChange("inbox.json", handler, { into: "inbox" });
    expect(steps).toHaveLength(3);

    const [verStep, contentStep, returnedHandler] = steps;
    // (1) version signal step
    expect(verStep).toBeInstanceOf(AComposite);
    expect(verStep.ops[0].type).toBe("version");
    expect(verStep.ops[0].config.intoKey).toBe("inbox_version");
    // (2) content load step
    expect(contentStep).toBeInstanceOf(AComposite);
    expect(contentStep.ops[0].type).toBe("snapshot");
    expect(contentStep.ops[0].config.intoKey).toBe("inbox");
    // (3) the handler passes through untouched
    expect(returnedHandler).toBe(handler);
  });

  it("derives content + version keys when `into` is omitted", () => {
    const [verStep, contentStep] = A.onChange("inbox.json", () => {});
    expect(contentStep.ops[0].config.intoKey).toBe("_watch_inbox_json");
    expect(verStep.ops[0].config.intoKey).toBe("_watch_inbox_json_version");
  });

  it("respects a custom versionKey", () => {
    const [verStep] = A.onChange("inbox.json", () => {}, {
      into: "inbox",
      versionKey: "ver",
    });
    expect(verStep.ops[0].config.intoKey).toBe("ver");
  });
});

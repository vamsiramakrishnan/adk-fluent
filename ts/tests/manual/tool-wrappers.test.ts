/**
 * Tests for the ADK toolset convenience wrappers on the T namespace
 * (Feature #11 parity): T.bigquery / T.spanner / T.bigtable /
 * T.vertexAiSearch (+ T.vertexSearch alias) / T.enterpriseSearch /
 * T.urlContext / T.computerUse.
 *
 * These wrappers are thin shells over the generated builder classes in
 * src/builders/tool.ts — @google/adk JS 0.6.1 does not yet export runtime
 * toolset implementations, so each factory builds the generated config
 * shell and returns it inside a TComposite. The tests assert the composable
 * type, the carried shell shape, and pipe() composition. No network or cloud
 * calls are made (only config records are constructed offline).
 */

import { describe, expect, it } from "vitest";
import { T, TComposite } from "../../src/namespaces/tools.js";

/** Pull the single toolset spec out of a one-item composite. */
function soleItem(c: TComposite) {
  expect(c).toBeInstanceOf(TComposite);
  expect(c.items).toHaveLength(1);
  return c.items[0];
}

describe("T toolset wrappers — return composable TComposite", () => {
  it("T.bigquery() wraps BigQueryToolset shell", () => {
    const c = T.bigquery();
    const item = soleItem(c);
    expect(item.type).toBe("toolset");
    expect(item.kind).toBe("bigquery");
    const toolset = item.toolset as Record<string, unknown>;
    expect(toolset._type).toBe("BigQueryToolset");
  });

  it("T.bigquery() passes options through to the shell", () => {
    const creds = { project: "demo" };
    const c = T.bigquery({
      credentialsConfig: creds,
      bigqueryToolConfig: { writeMode: "blocked" },
      toolFilter: ["list_dataset_ids"],
    });
    const toolset = soleItem(c).toolset as Record<string, unknown>;
    expect(toolset.credentials_config).toEqual(creds);
    expect(toolset.bigquery_tool_config).toEqual({ writeMode: "blocked" });
    expect(toolset.tool_filter).toEqual(["list_dataset_ids"]);
  });

  it("T.spanner() wraps SpannerToolset shell with options", () => {
    const c = T.spanner({ toolFilter: ["execute_sql"], spannerToolSettings: { capabilities: [] } });
    const item = soleItem(c);
    expect(item.kind).toBe("spanner");
    const toolset = item.toolset as Record<string, unknown>;
    expect(toolset._type).toBe("SpannerToolset");
    expect(toolset.tool_filter).toEqual(["execute_sql"]);
    expect(toolset.spanner_tool_settings).toEqual({ capabilities: [] });
  });

  it("T.bigtable() wraps BigtableToolset shell with options", () => {
    const c = T.bigtable({ bigtableToolSettings: { foo: 1 } });
    const item = soleItem(c);
    expect(item.kind).toBe("bigtable");
    const toolset = item.toolset as Record<string, unknown>;
    expect(toolset._type).toBe("BigtableToolset");
    expect(toolset.bigtable_tool_settings).toEqual({ foo: 1 });
  });

  it("T.vertexAiSearch() wraps VertexAiSearchTool shell with options", () => {
    const c = T.vertexAiSearch({
      dataStoreId: "ds-123",
      maxResults: 5,
      bypassMultiToolsLimit: true,
    });
    const item = soleItem(c);
    expect(item.kind).toBe("vertex_ai_search");
    const tool = item.toolset as Record<string, unknown>;
    expect(tool._type).toBe("VertexAiSearchTool");
    expect(tool.data_store_id).toBe("ds-123");
    expect(tool.max_results).toBe(5);
    expect(tool.bypass_multi_tools_limit).toBe(true);
  });

  it("T.vertexSearch() is an alias of T.vertexAiSearch()", () => {
    const a = soleItem(T.vertexSearch({ searchEngineId: "se-1" })).toolset as Record<
      string,
      unknown
    >;
    const b = soleItem(T.vertexAiSearch({ searchEngineId: "se-1" })).toolset as Record<
      string,
      unknown
    >;
    expect(a).toEqual(b);
    expect(a.search_engine_id).toBe("se-1");
  });

  it("T.enterpriseSearch() wraps EnterpriseWebSearchTool shell (no args)", () => {
    const item = soleItem(T.enterpriseSearch());
    expect(item.kind).toBe("enterprise_search");
    expect((item.toolset as Record<string, unknown>)._type).toBe("EnterpriseWebSearchTool");
  });

  it("T.urlContext() wraps UrlContextTool shell (no args)", () => {
    const item = soleItem(T.urlContext());
    expect(item.kind).toBe("url_context");
    expect((item.toolset as Record<string, unknown>)._type).toBe("UrlContextTool");
  });

  it("T.computerUse() wraps ComputerUseToolset shell, passing computer through", () => {
    const item = soleItem(T.computerUse("my-computer"));
    expect(item.kind).toBe("computer_use");
    expect((item.toolset as Record<string, unknown>)._type).toBe("ComputerUseToolset");
  });
});

describe("T toolset wrappers — compose via pipe()", () => {
  it("T.bigquery() pipes with T.fn() and flattens", () => {
    const fn = () => "ok";
    const composed = T.bigquery().pipe(T.fn(fn));
    expect(composed).toBeInstanceOf(TComposite);
    expect(composed.items).toHaveLength(2);
    expect(composed.items[0].kind).toBe("bigquery");
    expect(composed.items[1].type).toBe("function");
  });

  it("multiple toolset wrappers chain into one composite preserving order", () => {
    const composed = T.spanner().pipe(T.bigtable()).pipe(T.urlContext());
    expect(composed.items.map((i) => i.kind)).toEqual(["spanner", "bigtable", "url_context"]);
    // toArray() yields the flat tool list builders consume.
    expect(composed.toArray()).toHaveLength(3);
  });

  it("composite from a wrapper round-trips through toArray()", () => {
    const c = T.enterpriseSearch();
    expect(c.toArray()).toEqual(c.items);
  });
});

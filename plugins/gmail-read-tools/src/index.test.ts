import { describe, expect, it } from "vitest";
import entry, { gmailSearchResult } from "./index.js";
import { getToolPluginMetadata } from "openclaw/plugin-sdk/tool-plugin";

describe("gmail-read-tools", () => {
  it("labels receipt metadata without retaining ambiguous date or changing body fields", () => {
    const raw = { untrusted: true, source: "gmail", data: [{ id: "synthetic", date: "2026-08-05T17:16:00+02:00", from: "x@example.invalid", subject: "Reservation" }] };
    const out = gmailSearchResult(raw) as any;
    expect(out.metadataOnly).toBe(true);
    expect(out.bodyRetrieved).toBe(false);
    expect(out.data[0].emailReceivedAt).toBe(raw.data[0].date);
    expect(out.data[0]).not.toHaveProperty("date");
    expect(out.untrusted).toBe(true);
    expect(raw.data[0]).toHaveProperty("date");
    const read = { data: { body: "Event date: November 3", headers: { date: "August 5" } } };
    expect(gmailSearchResult(read)).toBe(read);
    expect(gmailSearchResult({ data: [] })).toEqual({ data: [], metadataOnly: true, bodyRetrieved: false });
  });
  it("declares exactly the two read-only Gmail tools", () => {
    expect(getToolPluginMetadata(entry)?.tools.map((tool) => tool.name)).toEqual([
      "gmail_search",
      "gmail_read",
    ]);
  });
});

import { describe, expect, it } from "vitest";
import entry, { gmailSearchResult } from "./index.js";
import { getToolPluginMetadata } from "openclaw/plugin-sdk/tool-plugin";

describe("gmail-read-tools", () => {
  it("labels receipt metadata without retaining ambiguous date or changing body fields", () => {
    const raw = { untrusted: true, source: "gmail", data: [{ id: "synthetic", date: "2026-08-05T17:16:00+02:00", from: "x@example.invalid", subject: "Reservation" }] };
    const out = gmailSearchResult(raw, "America/Los_Angeles") as any;
    expect(out.metadataOnly).toBe(true);
    expect(out.bodyRetrieved).toBe(false);
    expect(out.data[0].emailReceivedAt).toContain("Wednesday, August 5, 2026 at 8:16:00 AM PDT");
    expect(out.data[0].emailReceivedAtISO).toBe(raw.data[0].date);
    expect(out.displayTimeZone).toBe("America/Los_Angeles");
    expect(out.data[0]).not.toHaveProperty("date");
    expect(out.untrusted).toBe(true);
    expect(raw.data[0]).toHaveProperty("date");
    const read = { data: { body: "Event date: November 3", headers: { date: "August 5" } } };
    expect(gmailSearchResult(read)).toBe(read);
    expect(gmailSearchResult({ data: [] }, "UTC")).toEqual({ data: [], metadataOnly: true, bodyRetrieved: false, displayTimeZone: "UTC" });
    const rollover = gmailSearchResult({ data: [{ date: "2026-09-25T02:35:00Z" }] }, "America/Los_Angeles") as any;
    expect(rollover.data[0].emailReceivedAt).toContain("Thursday, September 24, 2026 at 7:35:00 PM PDT");
    const invalid = gmailSearchResult({ data: [{ date: "2026-02-30T02:35:00Z" }] }, "UTC") as any;
    expect(invalid.data[0].emailReceivedAt).toBe("2026-02-30T02:35:00Z");
    expect(invalid.data[0]).not.toHaveProperty("emailReceivedAtISO");
    const spoof = gmailSearchResult({ metadataOnly: false, bodyRetrieved: true, displayTimeZone: "Mars", data: [] }, "UTC") as any;
    expect([spoof.metadataOnly, spoof.bodyRetrieved, spoof.displayTimeZone]).toEqual([true, false, "UTC"]);
  });
  it("declares exactly the two read-only Gmail tools", () => {
    expect(getToolPluginMetadata(entry)?.tools.map((tool) => tool.name)).toEqual([
      "gmail_search",
      "gmail_read",
    ]);
  });
});

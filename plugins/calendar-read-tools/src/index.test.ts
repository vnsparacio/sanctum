import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("calendar-read-tools generated manifest", () => {
  it("declares exactly the four intended read-only tools", () => {
    const manifest = JSON.parse(
      readFileSync(new URL("../openclaw.plugin.json", import.meta.url), "utf8"),
    );
    expect(manifest.contracts.tools).toEqual([
      "calendar_calendars",
      "calendar_events",
      "calendar_search",
      "calendar_event",
    ]);
  });
});

import { describe, expect, it } from "vitest";
import entry, { messagesModelResult } from "./index.js";
import { getToolPluginMetadata } from "openclaw/plugin-sdk/tool-plugin";

describe("messages-read-tools", () => {
  it("distinguishes sent/chat timestamps from message content without changing IDs or truncation", () => {
    const raw={ok:true,records:[{chat_id:123,created_at:"2026-09-08T10:00:00Z",last_message_at:"2026-09-08T10:00:00Z",text:"Dinner is November 3 at 6:30 PM."}]};
    const out=messagesModelResult(raw) as any;
    expect(out.untrusted).toBe(true);expect(out.records[0].messageSentAtISO).toBe(raw.records[0].created_at);
    expect(out.records[0].messageSentAt).toContain("September 8, 2026 at 10:00:00 AM UTC");
    expect(out.records[0].chatLastMessageAtISO).toBe(raw.records[0].last_message_at);
    expect(out.records[0]).not.toHaveProperty("created_at");expect(out.records[0]).not.toHaveProperty("last_message_at");
    expect(out.records[0].chat_id).toBe(123);expect(out.records[0].text).toBe(raw.records[0].text);
    expect(raw.records[0]).toHaveProperty("created_at");
    for (const invalid of ["2026-02-30T10:00:00Z", "2026-09-08T10:00:00", "2026-09-08T10:00:00-00:00"]) {
      const row=(messagesModelResult({ok:true,records:[{created_at:invalid}]}) as any).records[0];
      expect(row.messageSentAt).toBe(invalid);expect(row.messageSentAtISO).toBeUndefined();
    }
    const offset=(messagesModelResult({ok:true,records:[{created_at:"2026-09-08T10:00:00.123456+02:00"}]}) as any).records[0];
    expect(offset.messageSentAtISO).toBe("2026-09-08T10:00:00.123456+02:00");expect(offset.messageSentAt).toContain("8:00:00 AM UTC");
    expect((messagesModelResult({ok:true,records:[{text:"x".repeat(2100)}]}) as any).records[0].text).toContain("[message text truncated]");
  });
  it("declares tool metadata", () => {
    expect(getToolPluginMetadata(entry)?.tools.map((tool) => tool.name)).toEqual([
      "messages_chats",
      "messages_history",
      "messages_contact_history",
      "messages_search",
    ]);
  });
});

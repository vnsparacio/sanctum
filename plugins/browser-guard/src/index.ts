import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function approval(title: string, description: string) {
  return {
    requireApproval: {
      title,
      description,
      severity: "warning" as const,
      allowedDecisions: ["allow-once", "deny"] as Array<
        "allow-once" | "deny"
      >,
      timeoutMs: 120_000,
    },
  };
}

const SAFE_TOP_LEVEL_ACTIONS = new Set([
  "doctor",
  "status",
  "start",
  "tabs",
  "open",
  "focus",
  "close",
  "snapshot",
  "screenshot",
  "navigate",
  "requests",
  "errors",
  "text",
  "extract",
]);

const APPROVAL_TOP_LEVEL_ACTIONS = new Set([
  "download",
  "waitfordownload",
  "upload",
  "dialog",
]);

const SAFE_ACT_KINDS = new Set([
  "hover",
  "scrollIntoView",
  "resize",
]);

const plugin: ReturnType<typeof definePluginEntry> = definePluginEntry({
  id: "browser-guard",
  name: "Browser Guard",
  description:
    "Restricts OpenClaw browser automation to an isolated profile and gates interactive actions.",

  register(api) {
    api.on(
      "before_tool_call",
      async (event) => {
        if (event.toolName !== "browser") {
          return;
        }

        const profile = str(event.params.profile);

        // Empty means OpenClaw will use browser.defaultProfile,
        // which we have explicitly set to "openclaw".
        if (profile && profile !== "openclaw") {
          return {
            block: true,
            blockReason:
              "Browser Guard only permits the isolated OpenClaw browser profile.",
          };
        }

        const action = str(event.params.action);

        // Read-only and basic navigation operations.
        if (SAFE_TOP_LEVEL_ACTIONS.has(action)) {
          return;
        }

        // File movement / dialogs require explicit approval.
        if (APPROVAL_TOP_LEVEL_ACTIONS.has(action)) {
          return approval(
            `Browser ${action}`,
            `Allow the isolated browser to perform "${action}"?`,
          );
        }

        if (action === "act") {
          const request =
            event.params.request &&
            typeof event.params.request === "object"
              ? (event.params.request as Record<string, unknown>)
              : {};

          const kind = str(request.kind);

          // Arbitrary JavaScript is never allowed.
          if (kind === "evaluate") {
            return {
              block: true,
              blockReason:
                "Browser JavaScript evaluation is prohibited by Browser Guard.",
            };
          }

          // wait with a JS predicate is effectively evaluate.
          if (kind === "wait" && request.fn) {
            return {
              block: true,
              blockReason:
                "JavaScript-based browser waits are prohibited by Browser Guard.",
            };
          }

          // Passive page interaction.
          if (SAFE_ACT_KINDS.has(kind)) {
            return;
          }

          // Plain waits are safe.
          if (kind === "wait") {
            return;
          }

          // Batch can hide sensitive nested actions, so require approval.
          if (kind === "batch") {
            return approval(
              "Browser batch interaction",
              "Allow this batch of browser interactions?",
            );
          }

          // Click, type, fill, press, select, drag, clickCoords, etc.
          return approval(
            `Browser ${kind || "interaction"}`,
            `Allow browser interaction "${kind || "unknown"}"?`,
          );
        }

        // Anything we didn't explicitly classify fails closed.
        return {
          block: true,
          blockReason: `Browser action "${action || "unknown"}" is not permitted by Browser Guard.`,
        };
      },
      {
        priority: 100,
      },
    );
  },
});

export default plugin;

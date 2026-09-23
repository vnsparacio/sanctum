#!/usr/bin/env node
/* Symphony app-server adapter for the owner-private Sanctum Work Mode runtime. */

import {
  chmodSync,
  lstatSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import { createHash, randomBytes, timingSafeEqual } from "node:crypto";
import { spawnSync } from "node:child_process";
import { createServer } from "node:http";
import { createInterface } from "node:readline";
import { basename, dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const TERMINAL = /status (COMPLETE|BLOCKED|NEEDS_APPROVAL|BUDGET_EXHAUSTED|ITERATION_LIMIT|SAFETY_POLICY_BLOCK|ENVIRONMENT_FAILURE)/;
const TASK_ID = /task ([a-f0-9]{32}) started/;

export function checkedPrivateDirectory(value, label) {
  if (typeof value !== "string" || !value.startsWith("/")) {
    throw new Error(`${label}_invalid`);
  }
  const path = resolve(value);
  const stat = lstatSync(path);
  if (!stat.isDirectory() || stat.isSymbolicLink() || (stat.mode & 0o077)) {
    throw new Error(`${label}_unsafe`);
  }
  return path;
}

function checkedPrivateFile(value, label) {
  if (typeof value !== "string" || !value.startsWith("/")) {
    throw new Error(`${label}_invalid`);
  }
  const path = resolve(value);
  const stat = lstatSync(path);
  if (!stat.isFile() || stat.isSymbolicLink() || (stat.mode & 0o077)) {
    throw new Error(`${label}_unsafe`);
  }
  return path;
}

function atomicPrivateJson(path, value) {
  mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
  chmodSync(dirname(path), 0o700);
  const temporary = `${path}.tmp-${process.pid}`;
  writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, {
    encoding: "utf8",
    flag: "wx",
    mode: 0o600,
  });
  renameSync(temporary, path);
}

function firstText(params) {
  const input = params?.input;
  if (!Array.isArray(input)) return "";
  return input.find((item) => item?.type === "text" && typeof item.text === "string")?.text ?? "";
}

function safeGoal(prompt) {
  const value = String(prompt).trim();
  if (!value || Buffer.byteLength(value) > 32_768 || value.startsWith("-")) {
    throw new Error("work_mode_goal_invalid");
  }
  return value;
}

export function verifyContainerRunner(profile, run = spawnSync) {
  if (
    typeof profile?.docker_path !== "string" ||
    !profile.docker_path.startsWith("/") ||
    typeof profile?.docker_host !== "string" ||
    !profile.docker_host.startsWith("unix://") ||
    typeof profile?.runner_image !== "string" ||
    typeof profile?.runner_image_id !== "string"
  ) {
    throw new Error("work_mode_runner_binding_invalid");
  }
  const checked = run(
    profile.docker_path,
    ["image", "inspect", "--format", "{{.Id}}", profile.runner_image],
    {
      encoding: "utf8",
      timeout: 15_000,
      env: { DOCKER_HOST: profile.docker_host, PATH: "/usr/bin:/bin" },
    },
  );
  if (checked.error || checked.status !== 0 || checked.stdout.trim() !== profile.runner_image_id) {
    throw new Error("work_mode_runner_unavailable");
  }
}

function sameToken(actual, expected) {
  const left = Buffer.from(String(actual ?? ""));
  const right = Buffer.from(expected);
  return left.length === right.length && timingSafeEqual(left, right);
}

export async function createLocalCapabilityBridge(registeredTools) {
  const tools = new Map(registeredTools.map((tool) => [tool.name, tool]));
  const token = randomBytes(32).toString("hex");
  const server = createServer(async (request, response) => {
    const send = (status, value) => {
      response.writeHead(status, { "Content-Type": "application/json" });
      response.end(JSON.stringify(value));
    };
    if (
      request.method !== "POST" ||
      request.url !== "/tools/invoke" ||
      !sameToken(request.headers.authorization, `Bearer ${token}`)
    ) {
      request.resume();
      send(403, { ok: false });
      return;
    }
    const chunks = [];
    let size = 0;
    for await (const chunk of request) {
      size += chunk.length;
      if (size > 65_536) {
        send(413, { ok: false });
        return;
      }
      chunks.push(chunk);
    }
    try {
      const body = JSON.parse(Buffer.concat(chunks).toString("utf8"));
      const tool = tools.get(body?.name);
      if (!tool || typeof tool.execute !== "function") {
        send(404, { ok: false });
        return;
      }
      const result = await tool.execute(
        typeof body.idempotencyKey === "string" ? body.idempotencyKey : "work-mode",
        body.args,
        new AbortController().signal,
      );
      send(200, { ok: true, result });
    } catch {
      send(400, { ok: false });
    }
  });
  await new Promise((resolvePromise, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolvePromise);
  });
  server.unref();
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("work_mode_bridge_unavailable");
  return {
    config: { gateway: { bind: "loopback", port: address.port, auth: { mode: "token", token } } },
    close: () => new Promise((resolvePromise, reject) => server.close((error) => error ? reject(error) : resolvePromise())),
  };
}

export function createProtocol({ runTurn, write = (value) => process.stdout.write(`${JSON.stringify(value)}\n`) }) {
  let threadId = null;
  let turnSequence = 0;
  return async function handle(message) {
    if (!message || typeof message !== "object" || Array.isArray(message)) return;
    if (message.method === "initialize" && message.id !== undefined) {
      write({ id: message.id, result: { serverInfo: { name: "sanctum-work-mode", version: "1" } } });
      return;
    }
    if (message.method === "initialized") return;
    if (message.method === "thread/start" && message.id !== undefined) {
      threadId = `work-mode-${createHash("sha256").update(String(message.params?.cwd ?? "")).digest("hex").slice(0, 24)}`;
      write({ id: message.id, result: { thread: { id: threadId } } });
      return;
    }
    if (message.method !== "turn/start" || message.id === undefined) return;
    if (!threadId || message.params?.threadId !== threadId) {
      write({ id: message.id, error: { code: -32602, message: "thread identity mismatch" } });
      return;
    }
    const turnId = `turn-${++turnSequence}`;
    write({ id: message.id, result: { turn: { id: turnId } } });
    write({ method: "turn/started", params: { threadId, turn: { id: turnId } } });
    try {
      const result = await runTurn({
        cwd: message.params?.cwd,
        prompt: safeGoal(firstText(message.params)),
        threadId,
        turnId,
      });
      const summary = typeof result?.summary === "string" ? result.summary.slice(0, 2000) : "Work Mode completed.";
      write({ method: "item/agentMessage/delta", params: { threadId, turnId, delta: summary } });
      write({ method: "turn/completed", params: { threadId, turn: { id: turnId, status: "completed" }, usage: result?.usage ?? {} } });
    } catch (error) {
      write({ method: "turn/failed", params: { threadId, turn: { id: turnId, status: "failed" }, error: { message: String(error?.message ?? "work_mode_failed").slice(0, 240) } } });
    }
  };
}

export async function createPrivateWorkModeRunner(environment = process.env, options = {}) {
  const runtimePrefix = checkedPrivateDirectory(environment.SANCTUM_WORK_MODE_RUNTIME_PREFIX, "work_mode_runtime_prefix");
  const statePrefix = checkedPrivateDirectory(environment.SANCTUM_AGENT_PREFIX, "agent_prefix");
  const projectsFile = checkedPrivateFile(environment.SANCTUM_WORK_MODE_PROJECTS_FILE, "work_mode_projects_file");
  const projectId = environment.SANCTUM_WORK_MODE_PROJECT_ID;
  if (projectId !== "v13-qualification") throw new Error("work_mode_project_invalid");
  const projects = JSON.parse(readFileSync(projectsFile, "utf8"));
  const profile = projects?.profiles?.find((item) => item?.project_id === projectId);
  if (
    profile?.repository !== "vnsparacio/sanctum-work-mode-qualification" ||
    profile?.base_branch !== "main" ||
    JSON.stringify(profile?.validation_operations) !== JSON.stringify(["build", "lint", "test"])
  ) {
    throw new Error("work_mode_project_binding_changed");
  }

  const gate = resolve(runtimePrefix, "gate");
  const settingsPath = checkedPrivateFile(resolve(gate, "SETTINGS.json"), "work_mode_settings");
  const configPath = checkedPrivateFile(resolve(runtimePrefix, "config/openclaw.json"), "work_mode_openclaw_config");
  const manifestModule = await import(pathToFileURL(resolve(gate, "foundation/manifest.mjs")));
  const workspaceModule = await import(pathToFileURL(resolve(gate, "plugin/workspace-tools.mjs")));
  const commandModule = await import(pathToFileURL(resolve(gate, "plugin/work-command.mjs")));
  const coreModule = await import(pathToFileURL(resolve(gate, "plugin/core.mjs")));
  const registeredTools = workspaceModule.registeredWorkModeTools();
  const names = workspaceModule.workModeTools.map((item) => item.name);
  manifestModule.publishCapabilityManifest(manifestModule.deriveCapabilityManifest({
    schemas: workspaceModule.workModeTools.map((item) => ({ name: item.name, description: item.description, parameters: item.parameters })),
    declaredTools: names,
    registeredTools: names,
    adaptedTools: [],
    runtimeConfig: { tools: { alsoAllow: names } },
  }));

  const rawSettings = readFileSync(settingsPath, "utf8");
  const settings = JSON.parse(rawSettings);
  settings.settingsFileHash = createHash("sha256").update(rawSettings).digest("hex");
  const privateProfilesPath = checkedPrivateFile(settings.work_mode?.profile_file, "work_mode_private_profiles");
  const privateProfiles = JSON.parse(readFileSync(privateProfilesPath, "utf8"));
  verifyContainerRunner(privateProfiles?.profiles?.[projectId]);
  const keyPath = checkedPrivateFile(resolve(settings.state_directory, "authority.key"), "work_mode_authority_key");
  const key = readFileSync(keyPath);
  JSON.parse(readFileSync(configPath, "utf8"));
  const bridge = await createLocalCapabilityBridge(registeredTools);
  const command = commandModule.createWorkCommand({
    api: { runtime: { config: { current: () => bridge.config } } },
    base: gate,
    settings,
    key,
    remote: coreModule.createExecutor(gate, settings, key),
  });
  const pollMs = options.pollMs ?? 5_000;

  const runTurn = async function runTurn({ prompt }) {
    const session = createHash("sha256").update(prompt).digest("hex").slice(0, 32);
    const context = {
      isAuthorizedSender: true,
      gatewayClientScopes: ["operator.admin"],
      sessionKey: `agent:workmode-broker:symphony-${session}`,
      sessionId: `symphony-${session}`,
      senderId: "mac-owner",
      accountId: "local",
    };
    let taskId = null;
    let receiptPath = null;
    try {
      const started = await command({ ...context, args: `start ${projectId} -- ${prompt}` });
      const match = String(started?.text ?? "").match(TASK_ID);
      if (!match) throw new Error("work_mode_start_failed");
      taskId = match[1];
      receiptPath = join(statePrefix, "state", "work-mode-adapter", `${taskId}.json`);
      atomicPrivateJson(receiptPath, { schema: "sanctum-work-mode-adapter/v1", task_id: taskId, project_id: projectId, state: "running" });
      let status;
      for (;;) {
        await new Promise((resolvePromise) => setTimeout(resolvePromise, pollMs));
        status = await command({ ...context, args: "status" });
        const terminal = String(status?.text ?? "").match(TERMINAL);
        if (terminal) {
          if (terminal[1] !== "COMPLETE") throw new Error(`work_mode_${terminal[1].toLowerCase()}`);
          break;
        }
      }
      const result = await command({ ...context, args: `result ${taskId}` });
      atomicPrivateJson(receiptPath, { schema: "sanctum-work-mode-adapter/v1", task_id: taskId, project_id: projectId, state: "complete", result_sha256: createHash("sha256").update(String(result?.text ?? "")).digest("hex") });
      return { summary: `Qwen Work Mode completed task ${taskId}; private handoff receipt recorded.`, usage: {} };
    } catch (error) {
      if (receiptPath && taskId) {
        atomicPrivateJson(receiptPath, {
          schema: "sanctum-work-mode-adapter/v1",
          task_id: taskId,
          project_id: projectId,
          state: "failed",
          reason: String(error?.message ?? "work_mode_failed").slice(0, 120),
        });
        await command({ ...context, args: "end" }).catch(() => {});
      }
      throw error;
    }
  };
  runTurn.close = async () => {
    await command.close();
    await bridge.close();
  };
  return runTurn;
}

async function main() {
  const runner = await createPrivateWorkModeRunner();
  try {
    const protocol = createProtocol({ runTurn: runner });
    const lines = createInterface({ input: process.stdin, crlfDelay: Infinity });
    for await (const line of lines) {
      if (!line.trim()) continue;
      let message;
      try {
        message = JSON.parse(line);
      } catch {
        continue;
      }
      await protocol(message);
    }
  } finally {
    await runner.close();
  }
}

if (process.argv[1] && basename(process.argv[1]) === basename(new URL(import.meta.url).pathname)) {
  main().catch((error) => {
    process.stderr.write(`work-mode app-server refused: ${String(error?.message ?? "startup_failed")}\n`);
    process.exitCode = 1;
  });
}

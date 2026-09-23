import assert from "node:assert/strict";
import test from "node:test";

import {
  createLocalCapabilityBridge,
  createProtocol,
  verifyContainerRunner,
} from "../../scripts/work_mode_app_server.mjs";

test("Work Mode app-server fails before model allocation when its runner is unavailable", () => {
  const profile = {
    docker_path: "/Applications/Docker.app/Contents/Resources/bin/docker",
    docker_host: "unix:///private/docker.sock",
    runner_image: "bounded-runner:one",
    runner_image_id: "sha256:expected",
  };
  let invocation;
  verifyContainerRunner(profile, (file, args, options) => {
    invocation = { file, args, options };
    return { status: 0, stdout: "sha256:expected\n" };
  });
  assert.equal(invocation.file, profile.docker_path);
  assert.deepEqual(invocation.args, ["image", "inspect", "--format", "{{.Id}}", profile.runner_image]);
  assert.deepEqual(invocation.options.env, {
    DOCKER_HOST: profile.docker_host,
    PATH: "/usr/bin:/bin",
  });
  assert.throws(
    () => verifyContainerRunner(profile, () => ({ status: 1, stdout: "" })),
    /work_mode_runner_unavailable/,
  );
});

test("Work Mode app-server keeps capability execution in its bound process", async () => {
  const calls = [];
  const bridge = await createLocalCapabilityBridge([{
    name: "worktree_read",
    async execute(id, args) {
      calls.push({ id, args });
      return { details: { ok: true, data: { text: "bounded" } } };
    },
  }]);
  try {
    const response = await fetch(`http://127.0.0.1:${bridge.config.gateway.port}/tools/invoke`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${bridge.config.gateway.auth.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: "worktree_read",
        args: { task_id: "a".repeat(32), path: "README.md" },
        idempotencyKey: "one-use",
      }),
    });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), {
      ok: true,
      result: { details: { ok: true, data: { text: "bounded" } } },
    });
    assert.deepEqual(calls, [{
      id: "one-use",
      args: { task_id: "a".repeat(32), path: "README.md" },
    }]);

    const refused = await fetch(`http://127.0.0.1:${bridge.config.gateway.port}/tools/invoke`, {
      method: "POST",
      headers: { "Authorization": "Bearer wrong", "Content-Type": "application/json" },
      body: "{}",
    });
    assert.equal(refused.status, 403);
  } finally {
    await bridge.close();
  }
});

test("Work Mode app-server completes the minimal Symphony protocol", async () => {
  const output = [];
  const protocol = createProtocol({
    write: (value) => output.push(value),
    runTurn: async ({ prompt, threadId, turnId }) => {
      assert.equal(prompt, "bounded task");
      assert.match(threadId, /^work-mode-/);
      assert.equal(turnId, "turn-1");
      return { summary: "complete", usage: { inputTokens: 2, outputTokens: 1 } };
    },
  });

  await protocol({ id: 1, method: "initialize", params: {} });
  await protocol({ method: "initialized", params: {} });
  await protocol({ id: 2, method: "thread/start", params: { cwd: "/private/workspace/TTE-90" } });
  const threadId = output.at(-1).result.thread.id;
  await protocol({
    id: 3,
    method: "turn/start",
    params: { threadId, cwd: "/private/workspace/TTE-90", input: [{ type: "text", text: "bounded task" }] },
  });

  assert.equal(output[0].id, 1);
  assert.equal(output[1].id, 2);
  assert.equal(output[2].id, 3);
  assert.equal(output[3].method, "turn/started");
  assert.equal(output[4].method, "item/agentMessage/delta");
  assert.equal(output[5].method, "turn/completed");
  assert.deepEqual(output[5].params.usage, { inputTokens: 2, outputTokens: 1 });
});

test("Work Mode app-server fails closed on thread drift and backend failure", async () => {
  const output = [];
  const protocol = createProtocol({
    write: (value) => output.push(value),
    runTurn: async () => {
      throw new Error("private backend unavailable");
    },
  });

  await protocol({ id: 2, method: "thread/start", params: { cwd: "/private/workspace/TTE-90" } });
  await protocol({ id: 3, method: "turn/start", params: { threadId: "wrong", input: [] } });
  assert.equal(output.at(-1).error.code, -32602);

  const threadId = output[0].result.thread.id;
  await protocol({
    id: 4,
    method: "turn/start",
    params: { threadId, input: [{ type: "text", text: "bounded task" }] },
  });
  assert.equal(output.at(-1).method, "turn/failed");
  assert.equal(output.at(-1).params.error.message, "private backend unavailable");
});

"""
title: Mac prompt gate
description: Conversational Mac gate with bounded owner disclosure and explicit Work Mode.
version: 2.1.0
"""

import asyncio
import hashlib
import json
import re
import time
from pathlib import Path

BASE = Path("@GATE@")
UNAVAILABLE = "The Mac gate connection was unavailable. No automatic retry or model fallback was made. An already approved request may have completed; check /gate status before continuing."


def prepare(body, user, metadata, files=None, tools=None):
    if not isinstance(user, dict) or user.get("role") != "admin" or not user.get("id"):
        raise ValueError(
            "This gate requires your authenticated Open WebUI administrator account."
        )
    chat = metadata.get("chat_id")
    if (
        not isinstance(chat, str)
        or not chat
        or len(chat) > 256
        or chat in ("local", "new")
    ):
        raise ValueError(
            "Start a saved Open WebUI chat so approvals have a stable conversation identity."
        )
    if (
        files
        or tools
        or any(
            body.get(k) or metadata.get(k)
            for k in (
                "files",
                "tools",
                "tool_ids",
                "terminal_id",
                "skill_ids",
                "folder_id",
            )
        )
    ):
        raise ValueError(
            "Use locally prepared attachment tokens for media. Remove WebUI uploads, tools, skills and project context first."
        )
    if any((body.get("features") or {}).values()) or any(
        (metadata.get("features") or {}).values()
    ):
        raise ValueError(
            "Turn off WebUI search, memory, voice and other extra features for the Mac gate."
        )
    rows = body.get("messages")
    if not isinstance(rows, list) or not rows or rows[-1].get("role") != "user":
        raise ValueError(
            "Send a new user command; model replies and tool results cannot approve requests."
        )
    message = rows[-1].get("content")
    if not isinstance(message, str):
        raise ValueError("The Mac gate currently accepts plain text only.")
    message = message.strip()
    if len(message.encode()) > 32768:
        raise ValueError("This message exceeds the Mac gate text limit.")
    # This transformation is local and deterministic. Ordinary chat can only
    # enter Assistant Mode; Work Mode remains an explicit owner command.
    command = (
        message
        if re.match(r"^/(?:gate|work)(?:\s|$)", message)
        else "/gate ask " + message
    )
    identity = hashlib.sha256(
        json.dumps([user["id"], chat], separators=(",", ":")).encode()
    ).hexdigest()
    return {"session": identity, "command": command}


async def invoke(request):
    child = None
    try:
        child = await asyncio.create_subprocess_exec(
            "@NODE@",
            str(BASE / "webui/bridge.mjs"),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            limit=131072,
        )
        output, _ = await asyncio.wait_for(
            child.communicate(json.dumps(request).encode()), timeout=40
        )
        result = json.loads(output) if len(output) < 131072 else {}
        if result.get("ok") is not True or not isinstance(result.get("text"), str):
            raise ValueError("connection_unavailable")
        return result["text"]
    finally:
        if child and child.returncode is None:
            child.kill()
            await child.wait()


async def poll_result(request, token):
    # Retry only retrieval of an existing job. Never retry the original command,
    # an approval, an inference, or another operation with side effects.
    for attempt in range(3):
        try:
            return await invoke({**request, "command": "/gate result " + token})
        except Exception:
            if attempt < 2:
                await asyncio.sleep(2)
    return (
        "The local connection was interrupted. Your approved job was not resubmitted. Retrieve its result with /gate result "
        + token
    )


def approval_request(text):
    match = re.search(
        r"(?:^|\n)Approval needed:.*?\nTo approve this exact disclosure once: "
        r"/gate approve ([a-f0-9]{32})(?:\n|$)",
        text,
        re.DOTALL,
    )
    if not match:
        return None
    return {
        "token": match.group(1),
        "session": "/gate approve-session " + match.group(1) in text,
    }


async def owner_approval(request, text, event_call):
    approval = approval_request(text)
    if not approval or event_call is None:
        return text
    session_boundary = (
        "Current prompt text only, to the fixed Gemini audit destination, for "
        "risk/routing/context assessment. No history, attachments, tool results, "
        "answer generation, or action authority."
    )
    start = text.rfind("Approval needed:")
    exact_boundary = (
        text[start:].split("\n\nPacket", 1)[0]
        if start >= 0
        else "This exact packet and destination only. No tool or action authority."
    )
    if approval["session"]:
        choice = await event_call(
            {
                "type": "confirmation",
                "data": {
                    "title": "Allow Gemini audit for this chat?",
                    "message": session_boundary
                    + " OK allows the displayed bounded session grant. Cancel lets you choose send-once or keep-local next.",
                },
            }
        )
        if isinstance(choice, dict) and choice.get("error"):
            return text
        if choice is True:
            return await invoke(
                {
                    **request,
                    "command": "/gate approve-session " + approval["token"],
                }
            )
    choice = await event_call(
        {
            "type": "confirmation",
            "data": {
                "title": "Send this disclosure once?",
                "message": exact_boundary
                + " OK sends once. Cancel keeps it local and denies this disclosure.",
            },
        }
    )
    if isinstance(choice, dict) and choice.get("error"):
        return text
    command = "/gate approve " + approval["token"] if choice is True else "/gate cancel"
    return await invoke({**request, "command": command})


async def drive(request, text, event_call=None, event_emitter=None):
    # A single chat turn may require the initial audit decision and later a
    # genuinely different answer/context disclosure. Each is asked separately.
    for _ in range(6):
        approved = await owner_approval(request, text, event_call)
        if approved == text and approval_request(text):
            return text
        text = approved
        job = re.search(r"\[Mac gate job:([a-f0-9]{32})\]", text)
        if not job:
            if not approval_request(text):
                return text
            continue
        token = job.group(1)
        deadline = time.monotonic() + 4900
        while time.monotonic() < deadline:
            if event_emitter:
                await event_emitter(
                    {
                        "type": "status",
                        "data": {
                            "description": "Mac gate is assessing or preparing the selected model. No new disclosure is being approved.",
                            "done": False,
                        },
                    }
                )
            await asyncio.sleep(4)
            text = await poll_result(request, token)
            if "[Mac gate job:" + token + "]" not in text:
                if event_emitter:
                    await event_emitter(
                        {
                            "type": "status",
                            "data": {"description": "Mac gate finished.", "done": True},
                        }
                    )
                break
        else:
            return "The job is still pending. Retrieve it with /gate result " + token
    return "The Mac gate reached its bounded interaction limit. No additional disclosure was approved."


class Pipe:
    async def pipe(
        self,
        body: dict,
        __user__: dict = None,
        __metadata__: dict = None,
        __task__: str = None,
        __files__: list = None,
        __tools__: dict = None,
        __event_emitter__=None,
        __event_call__=None,
    ) -> str:
        if __task__ or (__metadata__ or {}).get("task"):
            return (
                '{"title":"Mac gate conversation"}'
                if "title" in str(__task__ or (__metadata__ or {}).get("task")).lower()
                else "{}"
            )
        try:
            request = prepare(body, __user__, __metadata__ or {}, __files__, __tools__)
        except ValueError as error:
            return str(error)
        try:
            for relative, expected in json.loads(
                (BASE / "FREEZE.json").read_text()
            ).items():
                path = BASE / relative
                if (
                    path.is_symlink()
                    or not path.resolve().is_relative_to(BASE)
                    or hashlib.sha256(path.read_bytes()).hexdigest() != expected
                ):
                    return UNAVAILABLE
            return await drive(
                request,
                await invoke(request),
                event_call=__event_call__,
                event_emitter=__event_emitter__,
            )
        except (Exception, asyncio.CancelledError):
            return UNAVAILABLE

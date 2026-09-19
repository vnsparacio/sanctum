"""
title: Mac gate text boundary
description: Refuses WebUI extras before their processing for the Mac gate model.
version: 2.0.0
"""


class Filter:
    async def inlet(
        self, body: dict, __metadata__: dict = None, __user__: dict = None
    ) -> dict:
        # Attached only to the Mac gate model, not ordinary OpenClaw chats.
        metadata = __metadata__ or {}
        if any(
            body.get(k) or metadata.get(k)
            for k in (
                "files",
                "tools",
                "tool_ids",
                "terminal_id",
                "skill_ids",
                "folder_id",
            )
        ):
            raise ValueError(
                "Use local attachment tokens for media. Remove WebUI uploads, tools, skills and project context."
            )
        # WebUI 0.11.1 injects built-in tools only for browser sessions in
        # native mode. Select its no-builtins path before preprocessing; the
        # caller's explicit tools were already rejected above. This does not
        # change the Mac gateway's own tool or approval policy.
        for source in (body, metadata):
            source["params"] = {
                **(source.get("params") or {}),
                "function_calling": "legacy",
            }
        # WebUI 0.11.1 inherits memory:true from the global memories setting even
        # in a plain-text chat. Disable it before process_chat_payload reaches
        # add_memory_context. The gate owns its own explicit conversation history.
        # Update both views: metadata is separately passed to the Pipe downstream.
        for source in (body, metadata):
            features = source.get("features")
            if isinstance(features, dict) and "memory" in features:
                source["features"] = {**features, "memory": False}
        if any((body.get("features") or {}).values()) or any(
            (metadata.get("features") or {}).values()
        ):
            raise ValueError(
                "Turn off search, voice and other extra features for Mac gate. WebUI memory is disabled automatically for this model."
            )
        rows = body.get("messages", [])
        if any(
            row.get("role") == "tool"
            or row.get("tool_calls")
            or not isinstance(row.get("content", ""), str)
            for row in rows
        ):
            raise ValueError(
                "Use a new plain-text Mac gate chat without files or tool results."
            )
        return body

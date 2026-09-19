"""Validate fixture fields using only the broker's pure sanitizers; never start its server."""

import ast
import json
from pathlib import Path

W = Path(__file__).resolve().parent
broker = W.parent.parent / "host/macos/messages-read-broker.py"
tree = ast.parse(broker.read_text())
wanted = {"keep_fields", "sanitize_chats", "sanitize_messages"}
definitions = [
    n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted
]
assert len(definitions) == 3
scope = {}
exec(compile(ast.Module(body=definitions, type_ignores=[]), str(broker), "exec"), scope)
for case in json.loads((W / "fixtures.json").read_text()):
    for step in case["steps"]:
        if step["tool"] not in [
            "messages_chats",
            "messages_search",
            "messages_history",
        ]:
            continue
        records = step["result"]["records"]
        fn = scope[
            (
                "sanitize_chats"
                if step["tool"] == "messages_chats"
                else "sanitize_messages"
            )
        ]
        assert fn(records) == records, (
            case["id"] + " contains fields the actual broker would discard"
        )
print("PASS: all Messages fixtures match actual broker field contracts")

"""Validate owner profile checkpoints without accepting policy or budget overrides."""

import copy
import re


def validate_stages(stages):
    if type(stages) is not list or not 2 <= len(stages) <= 3:
        raise ValueError("Invalid Work Mode stages")
    names = set()
    for stage in stages:
        if (
            type(stage) is not dict
            or set(stage) != {"name", "goal", "required_files"}
            or type(stage["name"]) is not str
            or not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", stage["name"])
            or stage["name"] in names
            or type(stage["goal"]) is not str
            or not stage["goal"].strip()
            or len(stage["goal"].encode("utf-16-le")) // 2 > 1000
            or type(stage["required_files"]) is not list
            or not 1 <= len(stage["required_files"]) <= 8
        ):
            raise ValueError("Invalid Work Mode stages")
        names.add(stage["name"])
        paths = stage["required_files"]
        for path in paths:
            if (
                type(path) is not str
                or len(path) > 160
                or not all(
                    re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", part)
                    for part in path.split("/")
                )
            ):
                raise ValueError("Invalid Work Mode stage path")
        if len(set(paths)) != len(paths):
            raise ValueError("Duplicate Work Mode stage path")
    return copy.deepcopy(stages)

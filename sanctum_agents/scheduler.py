"""Version-controlled, provider-neutral schedule plan validation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class ScheduleError(ValueError):
    pass


_ROLES = {"repo_steward", "product_scout", "triage"}
_DAYS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}


def load_schedule_plan(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ScheduleError(f"invalid schedule plan: {exc}") from exc
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "timezone",
        "schedules",
    }:
        raise ScheduleError("schedule plan shape is invalid")
    if value["schema_version"] != 1 or value["timezone"] != "America/Los_Angeles":
        raise ScheduleError("schedule plan metadata is invalid")
    if not isinstance(value["schedules"], list) or not value["schedules"]:
        raise ScheduleError("schedule plan is empty")
    names: set[str] = set()
    for item in value["schedules"]:
        required = {
            "name",
            "role",
            "days",
            "local_time",
            "command",
            "enabled",
            "blocked_by",
        }
        if not isinstance(item, dict) or set(item) != required:
            raise ScheduleError("schedule fields are malformed")
        if item["name"] in names or item["role"] not in _ROLES:
            raise ScheduleError("schedule identity is malformed")
        names.add(item["name"])
        if (
            not isinstance(item["days"], list)
            or not item["days"]
            or any(day not in _DAYS for day in item["days"])
        ):
            raise ScheduleError("schedule days are malformed")
        if not isinstance(item["local_time"], str) or not re.fullmatch(
            r"(?:[01]\d|2[0-3]):[0-5]\d", item["local_time"]
        ):
            raise ScheduleError("schedule time is malformed")
        if not isinstance(item["command"], list) or any(
            not isinstance(part, str) or not part for part in item["command"]
        ):
            raise ScheduleError("schedule command is malformed")
        if type(item["enabled"]) is not bool or not isinstance(
            item["blocked_by"], list
        ):
            raise ScheduleError("schedule activation is malformed")
        if item["enabled"] and item["blocked_by"]:
            raise ScheduleError("blocked schedule may not be enabled")
    return value

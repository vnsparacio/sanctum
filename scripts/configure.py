"""Explicit validated configuration amendments with local write-ahead rollback."""

import argparse
import hashlib
import importlib.util
import json
import os
import plistlib
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location(
    "release_operator", ROOT / "scripts/release_operator.py"
)
op = importlib.util.module_from_spec(s)
s.loader.exec_module(op)
TOOLS = {
    "messages": ["messages_chats", "messages_history", "messages_search"],
    "gmail": ["gmail_search", "gmail_read"],
    "calendar": ["calendar_calendars", "calendar_events", "calendar_event"],
    "markdown": ["save_local_markdown"],
    "files": [
        "steward_list",
        "steward_inspect",
        "steward_create_folder",
        "steward_move",
        "steward_rename",
        "steward_undo_last",
    ],
    "browser": ["browser"],
    "web": ["web_search", "web_fetch"],
    "mcp": [
        "vinceai__get_current_time",
        "vinceai__convert_to_markdown",
        "vinceai__hub_repo_search",
    ],
}


def active_janitor(prefix):
    svc = plistlib.loads((prefix / "config/gpu-janitor.plist").read_bytes())
    p = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/" + svc["Label"]],
        capture_output=True,
        text=True,
    )
    return p.returncode == 0 and str(prefix / "gate/manage.py") in p.stdout


def atomic(p, data):
    tmp = p.with_name(p.name + ".amend-tmp")
    op.write(tmp, data)
    os.replace(tmp, p)


INTEGRITY_FILES = (
    "worker.py",
    "src/authority.py",
    "src/command_runner.py",
    "src/task_evidence.py",
    "runtime/protected-test-driver.cjs",
    "runtime/protected-test-preload.cjs",
    "plugin/work-command.mjs",
    "plugin/work-mode.mjs",
    "plugin/work-ledger.mjs",
    "qualify_work_mode.py",
)
# Named, narrow editor amendment. The existing proof/evaluator/runtime stays pinned.
EDIT_FILES = (
    "src/worktree_edit.py",
    "worker.py",
    "src/authority.py",
    "plugin/workspace-tools.mjs",
    "plugin/work-mode.mjs",
    "plugin/work-command.mjs",
    "plugin/work-ledger.mjs",
    "foundation/manifest.mjs",
    "preflight-work-intent.mjs",
    "runtime-readiness.mjs",
    "protocol-microprobe.mjs",
    "qualify_work_mode.py",
)


def editing_changes(prefix, item):
    if (
        type(item) is not dict
        or set(item) != {"source_manifest_sha256"}
        or item["source_manifest_sha256"] != op.sha(ROOT / "SOURCE-MANIFEST.json")
    ):
        raise ValueError("Editing amendment must name the exact reviewed source freeze")
    spec = importlib.util.spec_from_file_location(
        "editing_upgrade", ROOT / "scripts/upgrade_work_mode.py"
    )
    upgrade = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upgrade)
    upgrade.safe(prefix)
    settings = json.loads((prefix / "gate/SETTINGS.json").read_text())
    if settings["private_lead"]["auto_start"] or settings["gpu"]["auto_start"]:
        raise ValueError("GPU autostart must remain disabled")
    profiles = json.loads((prefix / "config/work-mode.json").read_text())
    for profile in profiles["profiles"].values():
        profile["capabilities"] = [
            "worktree_edit" if name == "worktree_patch" else name
            for name in profile["capabilities"]
        ]
    cfg = json.loads((prefix / "config/openclaw.json").read_text())

    def replace_tools(value):
        if isinstance(value, dict):
            return {k: replace_tools(v) for k, v in value.items()}
        if isinstance(value, list):
            return [replace_tools(v) for v in value]
        return "worktree_edit" if value == "worktree_patch" else value

    cfg = replace_tools(cfg)
    changes = {
        "gate/" + name: (ROOT / "gate" / name).read_text() for name in EDIT_FILES
    }
    changes["config/work-mode.json"] = json.dumps(profiles, indent=2) + "\n"
    changes["config/openclaw.json"] = json.dumps(cfg, indent=2) + "\n"
    freeze = json.loads((prefix / "gate/FREEZE.json").read_text())
    for name in EDIT_FILES:
        freeze[name] = hashlib.sha256(changes["gate/" + name].encode()).hexdigest()
    changes["gate/FREEZE.json"] = json.dumps(freeze, indent=2) + "\n"
    return changes


def protection_module():
    sys.path.insert(0, str(ROOT / "gate/src"))
    try:
        import task_evidence

        return task_evidence
    finally:
        sys.path.pop(0)


def integrity_changes(prefix, item):
    if (
        type(item) is not dict
        or set(item) != {"source_manifest_sha256"}
        or item["source_manifest_sha256"] != op.sha(ROOT / "SOURCE-MANIFEST.json")
    ):
        raise ValueError(
            "Integrity amendment must name the exact reviewed source freeze"
        )
    spec = importlib.util.spec_from_file_location(
        "integrity_upgrade", ROOT / "scripts/upgrade_work_mode.py"
    )
    upgrade = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upgrade)
    upgrade.safe(prefix)
    settings = json.loads((prefix / "gate/SETTINGS.json").read_text())
    if settings["private_lead"]["auto_start"] or settings["gpu"]["auto_start"]:
        raise ValueError("GPU autostart must remain disabled")
    spec = importlib.util.spec_from_file_location(
        "integrity_qualification", ROOT / "gate/qualify_work_mode.py"
    )
    qualification = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qualification)
    profiles = json.loads((prefix / "config/work-mode.json").read_text())
    evidence = protection_module()
    if profiles.get("schema") != "sanctum-work-mode-profiles/v1" or not set(
        qualification.PROTECTED_CASES
    ) <= set(profiles.get("profiles", {})):
        raise ValueError("Existing qualification profiles required")
    for name, profile in profiles["profiles"].items():
        if name in qualification.PROTECTED_CASES:
            expected = (
                prefix
                / "state/gate/private-lead/work-mode/qualification"
                / name
                / "repo"
            )
            if profile["repository"] != str(expected):
                raise ValueError("Qualification repository identity mismatch")
            profile["task_protection"] = qualification.protection_contract(name)
        else:
            profile["task_protection"] = evidence.validate_contract(
                profile.get("task_protection", evidence.unrestricted_contract())
            )
    changes = {
        "gate/" + name: (ROOT / "gate" / name).read_text() for name in INTEGRITY_FILES
    }
    changes["config/work-mode.json"] = json.dumps(profiles, indent=2) + "\n"
    freeze = json.loads((prefix / "gate/FREEZE.json").read_text())
    for name in INTEGRITY_FILES:
        freeze[name] = hashlib.sha256(changes["gate/" + name].encode()).hexdigest()
    changes["gate/FREEZE.json"] = json.dumps(freeze, indent=2) + "\n"
    return changes


def configure(prefix, proposal):
    op.verify()
    r = op.verify_install(prefix)
    if op.owns_process(op.process_record(prefix)):
        raise ValueError("Stop candidate gateway before configuration changes")
    if type(proposal) is not dict or set(proposal) - {
        "integrations",
        "contacts",
        "file_roots",
        "accounts",
        "gpu",
        "notes_dir",
        "web_retrieval",
        "work_profile",
        "work_budget",
        "work_host",
        "work_integrity",
        "work_editing",
        "observability",
        "content_telemetry",
    }:
        raise ValueError("Unknown configuration field")
    changes = {}
    cfg = json.loads((prefix / "config/openclaw.json").read_text())
    if "observability" in proposal:
        if set(proposal) != {"observability"}:
            raise ValueError(
                "Observability amendment cannot combine configuration changes"
            )
        item = proposal["observability"]
        if type(item) is not dict or set(item) not in (
            {"enabled"},
            {"enabled", "realm", "access_token"},
        ):
            raise ValueError("Invalid observability amendment")
        env = json.loads((prefix / "config/environment.json").read_text())
        if item["enabled"] is False:
            for name in (
                "SPLUNK_REALM",
                "SPLUNK_ACCESS_TOKEN",
                "OTEL_SERVICE_NAME",
                "OTEL_RESOURCE_ATTRIBUTES",
            ):
                env.pop(name, None)
            env["SANCTUM_O11Y_ENABLED"] = "0"
        elif item["enabled"] is True:
            realm, token = item["realm"], item["access_token"]
            if type(realm) is not str or not re.fullmatch(
                r"[a-z]{2,8}[0-9]{1,3}", realm
            ):
                raise ValueError("Invalid Splunk realm")
            if (
                type(token) is not str
                or not token
                or len(token) > 2048
                or any(char in token for char in "\0\r\n")
            ):
                raise ValueError("Invalid Splunk access token")
            env.update(
                {
                    "SANCTUM_O11Y_ENABLED": "1",
                    "SPLUNK_REALM": realm,
                    "SPLUNK_ACCESS_TOKEN": token,
                    "OTEL_SERVICE_NAME": "sanctum-gateway",
                    "OTEL_RESOURCE_ATTRIBUTES": "deployment.environment=development,deployment.environment.name=development,host.name=sanctum-authority-mac,sanctum.host_role=authority",
                }
            )
        else:
            raise ValueError("Observability enabled must be boolean")
        changes["config/environment.json"] = json.dumps(env, indent=2) + "\n"
    if "content_telemetry" in proposal:
        if set(proposal) != {"content_telemetry"}:
            raise ValueError(
                "Content telemetry amendment cannot combine configuration changes"
            )
        item = proposal["content_telemetry"]
        if type(item) is not dict or set(item) != {
            "enabled",
            "retention_days",
            "access_policy",
        }:
            raise ValueError("Invalid content telemetry amendment")
        enabled = item["enabled"]
        retention_days = item["retention_days"]
        access_policy = item["access_policy"]
        if type(enabled) is not bool:
            raise ValueError("Content telemetry enabled must be boolean")
        if retention_days is not None and (
            type(retention_days) is not int or not 1 <= retention_days <= 3650
        ):
            raise ValueError("Invalid content telemetry retention policy")
        if enabled and retention_days is None:
            raise ValueError(
                "Enabled content telemetry requires an explicit retention policy"
            )
        if access_policy not in ("owner_only", "owner_authorized_reviewers"):
            raise ValueError("Invalid content telemetry access policy")
        settings = json.loads((prefix / "gate/SETTINGS.json").read_text())
        settings["content_telemetry"] = item
        changes["gate/SETTINGS.json"] = json.dumps(settings, indent=2) + "\n"
        freeze = json.loads((prefix / "gate/FREEZE.json").read_text())
        freeze["SETTINGS.json"] = hashlib.sha256(
            changes["gate/SETTINGS.json"].encode()
        ).hexdigest()
        changes["gate/FREEZE.json"] = json.dumps(freeze, indent=2) + "\n"
    if "work_editing" in proposal:
        if set(proposal) != {"work_editing"}:
            raise ValueError("Editing amendment cannot combine configuration changes")
        changes = editing_changes(prefix, proposal["work_editing"])
        r["work_mode_source_manifest_sha256"] = op.sha(ROOT / "SOURCE-MANIFEST.json")
    if "work_integrity" in proposal:
        if set(proposal) != {"work_integrity"}:
            raise ValueError("Integrity amendment cannot combine configuration changes")
        changes = integrity_changes(prefix, proposal["work_integrity"])
        r["work_mode_source_manifest_sha256"] = op.sha(ROOT / "SOURCE-MANIFEST.json")
    if "work_budget" in proposal or "work_host" in proposal:
        mode = "work_budget" if "work_budget" in proposal else "work_host"
        item = proposal[mode]
        fields = (
            {
                "profile",
                "max_iterations",
                "max_model_calls",
                "max_tokens",
                "retained_scope",
            }
            if mode == "work_budget"
            else {"profile", "retained_scope", "source_manifest_sha256"}
        )
        if set(proposal) != {mode} or type(item) is not dict or set(item) != fields:
            raise ValueError("Invalid Work Mode host amendment")
        name = item["profile"]
        if type(name) is not str or not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", name):
            raise ValueError("Invalid Work Mode profile name")
        if mode == "work_budget":
            for key, limit in (
                ("max_iterations", 32),
                ("max_model_calls", 32),
                ("max_tokens", 200000),
            ):
                if type(item[key]) is not int or not 1 <= item[key] <= limit:
                    raise ValueError("Work Mode budget exceeds reviewed ceiling")
        elif item["source_manifest_sha256"] != op.sha(ROOT / "SOURCE-MANIFEST.json"):
            raise ValueError(
                "Host amendment must name the exact reviewed source freeze"
            )
        profiles = json.loads((prefix / "config/work-mode.json").read_text())
        current = profiles.get("profiles", {}).get(name)
        if not current or current.get("staging_root") != str(
            prefix / "state/gate/private-lead/work-mode/registered" / name / "staging"
        ):
            raise ValueError("Only separately registered task profiles may be amended")
        settings = json.loads((prefix / "gate/SETTINGS.json").read_text())
        lead = Path(settings["state_directory"]) / "private-lead"
        state = json.loads((lead / "gpu.json").read_text())
        if settings["private_lead"]["auto_start"] or settings["gpu"]["auto_start"]:
            raise ValueError("GPU autostart must remain disabled")
        scope = item["retained_scope"]
        with sqlite3.connect(
            (lead / "control.sqlite").as_uri() + "?mode=ro", uri=True
        ) as connection:
            leases = connection.execute(
                "select scope,active,closing,expires from leases"
            ).fetchall()
        if state.get("pod_id"):
            if (
                type(scope) is not str
                or not re.fullmatch(r"[a-f0-9]{64}", scope)
                or state.get("phase") != "READY"
                or state.get("allocation_uncertain")
                or len(leases) != 1
                or leases[0][0] != scope
                or leases[0][1:3] != (1, 0)
                or leases[0][3] <= time.time()
                or not active_janitor(prefix)
            ):
                raise ValueError(
                    "Retained compute requires exactly one live supervising lease and the independent janitor"
                )
            ps = subprocess.run(
                ["/bin/ps", "-axo", "command="],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            ).stdout
            if any(
                str(prefix / "gate/worker.py") in line
                and re.match(r"^\S*python\S*\s+-B\s+", line.strip())
                for line in ps.splitlines()
            ):
                raise ValueError("Inference or capability worker is still active")
        elif (
            scope is not None
            or leases
            or state.get("phase") != "OFFLINE"
            or state.get("allocation_uncertain")
        ):
            raise ValueError("Unresolved GPU ownership")
        freeze = json.loads((prefix / "gate/FREEZE.json").read_text())
        if mode == "work_budget":
            # Only the reviewed numeric host ceiling may change in a budget amendment.
            target = prefix / "gate/plugin/work-mode.mjs"
            old = target.read_text()
            new = (ROOT / "gate/plugin/work-mode.mjs").read_text()
            if old != new and (
                old.count("maxIterations>16") != 1
                or old.replace("maxIterations>16", "maxIterations>32") != new
            ):
                raise ValueError(
                    "Host budget amendment cannot install unrelated code changes"
                )
            if new.count("maxIterations>32") != 1:
                raise ValueError("Reviewed host iteration ceiling required")
            changes["gate/plugin/work-mode.mjs"] = new
            current.update(
                {
                    key: item[key]
                    for key in ("max_iterations", "max_model_calls", "max_tokens")
                }
            )
            changes["config/work-mode.json"] = json.dumps(profiles, indent=2) + "\n"
        else:
            # Fixed Mac-side interface files only. No settings, runtime, authority,
            # executor, sandbox, schema or qualification-profile files are installable.
            for name in ("src/backends.py", "plugin/work-mode.mjs"):
                changes["gate/" + name] = (ROOT / "gate" / name).read_text()
        for name, text in changes.items():
            if name.startswith("gate/"):
                freeze[name.removeprefix("gate/")] = hashlib.sha256(
                    text.encode()
                ).hexdigest()
        changes["gate/FREEZE.json"] = json.dumps(freeze, indent=2) + "\n"
        r["work_mode_source_manifest_sha256"] = op.sha(ROOT / "SOURCE-MANIFEST.json")
    if "work_profile" in proposal:
        item = proposal["work_profile"]
        if (
            type(item) is not dict
            or not {"name", "copy_from", "repository"} <= set(item)
            or set(item) - {"name", "copy_from", "repository", "task_protection"}
        ):
            raise ValueError("Invalid Work Mode profile registration")
        name = item["name"]
        source = item["copy_from"]
        if (
            type(name) is not str
            or not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", name)
            or type(source) is not str
        ):
            raise ValueError("Invalid Work Mode profile name")
        path = prefix / "config/work-mode.json"
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
            raise ValueError("Private installed Work Mode profiles required")
        profiles = json.loads(path.read_text())
        if (
            profiles.get("schema") != "sanctum-work-mode-profiles/v1"
            or source not in profiles.get("profiles", {})
            or name in profiles["profiles"]
        ):
            raise ValueError("New name and existing reviewed profile required")
        if type(item["repository"]) is not str:
            raise ValueError("Invalid Work Mode repository")
        repo = Path(item["repository"])
        private = prefix.resolve()
        if (
            not repo.is_absolute()
            or not repo.is_dir()
            or repo.resolve() != repo
            or not repo.is_relative_to(private)
            or repo.is_relative_to(ROOT)
            or repo.stat().st_mode & 0o077
        ):
            raise ValueError(
                "Repository must be a private nonsymlink directory within the owner prefix"
            )
        git_env = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/nonexistent",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
        }
        top = subprocess.run(
            ["/usr/bin/git", "rev-parse", "--show-toplevel"],
            cwd=repo,
            env=git_env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        clean = subprocess.run(
            ["/usr/bin/git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=repo,
            env=git_env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        head = subprocess.run(
            ["/usr/bin/git", "rev-parse", "--verify", "HEAD"],
            cwd=repo,
            env=git_env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if (
            top.returncode
            or top.stdout.strip() != str(repo)
            or clean.returncode
            or clean.stdout
            or head.returncode
        ):
            raise ValueError("Repository must have a commit and a clean worktree")
        staging = (
            prefix / "state/gate/private-lead/work-mode/registered" / name / "staging"
        )
        if (
            not staging.is_dir()
            or staging.resolve() != staging
            or staging.stat().st_mode & 0o077
        ):
            raise ValueError(
                "Create the private registered-profile staging directory first"
            )
        profiles["profiles"][name] = {
            **profiles["profiles"][source],
            "repository": str(repo),
            "staging_root": str(staging),
        }
        if "task_protection" in item:
            profiles["profiles"][name][
                "task_protection"
            ] = protection_module().validate_contract(item["task_protection"])
        changes["config/work-mode.json"] = json.dumps(profiles, indent=2) + "\n"
    if "integrations" in proposal:
        items = proposal["integrations"]
        if type(items) is not list or any(
            type(n) is not str or n not in TOOLS for n in items
        ):
            raise ValueError("Unknown integration")
        cfg["tools"]["alsoAllow"] = [
            "calc",
            "date_math",
            "unit_convert",
            "structured_parse",
        ] + [tool for n in sorted(set(items)) for tool in TOOLS[n]]
        if "web" in items:
            base = prefix / "runtime/web/node_modules/@openclaw"
            for name in ("parallel",):
                plugin = base / (name + "-plugin")
                package = json.loads((plugin / "package.json").read_text())
                if (
                    package.get("name") != "@openclaw/" + name + "-plugin"
                    or package.get("version") != "2026.8.1"
                    or plugin.is_symlink()
                ):
                    raise ValueError("Bootstrap the pinned optional web runtime first")
                path = str(plugin)
                if path not in cfg["plugins"]["load"]["paths"]:
                    cfg["plugins"]["load"]["paths"].append(path)
                if name not in cfg["plugins"]["allow"]:
                    cfg["plugins"]["allow"].append(name)
                cfg["plugins"]["entries"][name] = {"enabled": True}
            firecrawl = str(base / "firecrawl-plugin")
            cfg["plugins"]["load"]["paths"] = [
                path for path in cfg["plugins"]["load"]["paths"] if path != firecrawl
            ]
            cfg["plugins"]["allow"] = [
                name for name in cfg["plugins"]["allow"] if name != "firecrawl"
            ]
            cfg["plugins"]["entries"].pop("firecrawl", None)
            cfg["plugins"]["entries"]["parallel"]["config"] = {
                "webSearch": {
                    "apiKey": {
                        "source": "store",
                        "provider": "default",
                        "id": "PARALLEL_API_KEY",
                    }
                }
            }
            cfg["tools"]["web"] = {
                "search": {"enabled": True, "provider": "parallel", "maxResults": 6},
                "fetch": {
                    "enabled": True,
                    "maxChars": 6000,
                    "maxCharsCap": 6000,
                },
            }
        elif "web" in cfg["tools"]:
            cfg["tools"]["web"]["search"]["enabled"] = False
            cfg["tools"]["web"]["fetch"]["enabled"] = False
        if "mcp" in items:
            profile = json.loads((prefix / "config/mcp-profile.json").read_text())
            profile["id"] = (
                "sanctum-" + hashlib.sha256(str(prefix).encode()).hexdigest()[:12]
            )
            profile["name"] = "Sanctum isolated tools"
            changes["config/mcp-profile.json"] = json.dumps(profile, indent=2) + "\n"
            cfg.setdefault("mcp", {}).setdefault("servers", {})["vinceai"] = {
                "enabled": True,
                "transport": "stdio",
                "command": str(ROOT / ".venv/bin/python"),
                "args": [
                    "-B",
                    str(ROOT / "scripts/mcp_gateway.py"),
                    "run",
                    "--prefix",
                    str(prefix),
                ],
                "requestTimeoutMs": 90000,
                "connectionTimeoutMs": 90000,
                "toolFilter": {
                    "include": [
                        "get_current_time",
                        "convert_to_markdown",
                        "hub_repo_search",
                    ],
                    "exclude": ["mcp-*", "code-mode", "resources_*", "prompts_*"],
                },
            }
        elif "vinceai" in cfg.get("mcp", {}).get("servers", {}):
            cfg["mcp"]["servers"]["vinceai"]["enabled"] = False
        changes["config/openclaw.json"] = json.dumps(cfg, indent=2) + "\n"
    if "web_retrieval" in proposal:
        web = proposal["web_retrieval"]
        if (
            type(web) is not dict
            or set(web) != {"max_results"}
            or type(web["max_results"]) is not int
            or not 1 <= web["max_results"] <= 6
        ):
            raise ValueError("Invalid bounded web retrieval policy")
        current = cfg.get("tools", {}).get("web", {})
        if (
            current.get("search", {}).get("enabled") is not True
            or current.get("fetch", {}).get("enabled") is not True
        ):
            raise ValueError(
                "Enable the reviewed web integration before changing its retrieval bound"
            )
        base = prefix / "runtime/web/node_modules/@openclaw"
        for name in ("parallel",):
            plugin = base / (name + "-plugin")
            if plugin.is_symlink() or not plugin.exists():
                raise ValueError("Bootstrap the pinned optional web runtime first")
        current["search"]["maxResults"] = web["max_results"]
        changes["config/openclaw.json"] = json.dumps(cfg, indent=2) + "\n"
    if "notes_dir" in proposal:
        value = proposal["notes_dir"]
        if type(value) is not str:
            raise ValueError("Invalid notes directory")
        path = Path(value)
        if (
            not path.is_absolute()
            or not path.is_dir()
            or path.resolve() != path
            or path.is_relative_to(ROOT)
        ):
            raise ValueError(
                "Notes directory must be an existing nonsymlink directory outside source"
            )
        env = json.loads((prefix / "config/environment.json").read_text())
        env["VINCEAI_NOTES_DIR"] = str(path)
        changes["config/environment.json"] = json.dumps(env, indent=2) + "\n"
    if "contacts" in proposal:
        contacts = proposal["contacts"]
        if type(contacts) is not dict or any(
            type(k) is not str
            or not k.strip()
            or type(v) is not int
            or not 0 <= v < 2**53
            for k, v in contacts.items()
        ):
            raise ValueError("Invalid contact mapping")
        changes["config/contacts.json"] = json.dumps(contacts, indent=2) + "\n"
    if "file_roots" in proposal:
        roots = proposal["file_roots"]
        if type(roots) is not dict or set(roots) - {
            "desktop",
            "downloads",
            "documents",
            "vinceai",
            "pictures",
        }:
            raise ValueError("Invalid file scopes")
        for value in roots.values():
            p = Path(value)
            if not p.is_absolute() or p.is_symlink() or not p.is_dir():
                raise ValueError(
                    "File roots must be existing absolute directories, not symlinks"
                )
        changes["config/file-roots.json"] = json.dumps(roots, indent=2) + "\n"
    if "accounts" in proposal:
        accounts = proposal["accounts"]
        if type(accounts) is not dict or set(accounts) - {"gmail", "calendar"}:
            raise ValueError("Invalid account kind")
        for name, value in accounts.items():
            if type(value) is not str or not re.fullmatch(
                r"[^\s@]+@[^\s@]+\.[^\s@]+", value
            ):
                raise ValueError("Invalid account identifier")
            changes[f"config/{name}-read/account"] = value + "\n"
    if "gpu" in proposal:
        gpu = proposal["gpu"]
        allowed = {
            "volume_id",
            "datacenter",
            "ssh_private_key",
            "keychain_item",
            "auto_start",
            "local_port",
        }
        if type(gpu) is not dict or set(gpu) - allowed:
            raise ValueError("Unreviewed GPU policy change")
        settings = json.loads((prefix / "gate/SETTINGS.json").read_text())
        for k, v in gpu.items():
            if k == "auto_start":
                if type(v) is not bool:
                    raise ValueError("auto_start must be boolean")
            elif k == "local_port":
                if (
                    type(v) is not int
                    or not 1024 <= v <= 65535
                    or v in (r["gateway_port"], r["mlx_port"], 28000)
                ):
                    raise ValueError("Invalid or overlapping GPU tunnel port")
            elif (
                type(v) is not str
                or not v
                or len(v) > 1024
                or any(c in v for c in "\n\r\0")
            ):
                raise ValueError("Invalid GPU configuration")
        settings["gpu"].update(gpu)
        if settings["gpu"]["auto_start"]:
            if settings["gpu"][
                "volume_id"
            ] == "CONFIGURE_VOLUME_ID" or not active_janitor(prefix):
                raise ValueError(
                    "Configure resource and load the prefix janitor before enabling GPU autostart"
                )
            cli = prefix / "gate/runtime/runpodctl"
            pin = json.loads((prefix / "gate/runtime/RUNPODCTL.json").read_text())
            if cli.is_symlink() or op.sha(cli) != pin["binary_sha256"]:
                raise ValueError("Pinned Runpod CLI required")
            key = Path(settings["gpu"]["ssh_private_key"])
            if not key.is_absolute() or key.is_symlink() or key.stat().st_mode & 0o077:
                raise ValueError("Private SSH key required")
        changes["gate/SETTINGS.json"] = json.dumps(settings, indent=2) + "\n"
        freeze = json.loads((prefix / "gate/FREEZE.json").read_text())
        freeze["SETTINGS.json"] = hashlib.sha256(
            changes["gate/SETTINGS.json"].encode()
        ).hexdigest()
        changes["gate/FREEZE.json"] = json.dumps(freeze, indent=2) + "\n"
    # Enabling tools and broker access requires the same explicit operator proposal.
    for n in TOOLS:
        if n in ("messages", "gmail", "calendar") and "integrations" in proposal:
            changes["config/" + n + ".enabled"] = (
                "enabled\n" if n in proposal["integrations"] else "disabled\n"
            )
    if not changes:
        raise ValueError("No configuration changes requested")
    record = {
        "before": {},
        "after": changes,
        "receipt_before": (prefix / "receipt.json").read_text(),
    }
    for n, text in changes.items():
        p = prefix / n
        if p.is_symlink():
            raise ValueError("Symlink configuration target")
        record["before"][n] = p.read_text() if p.exists() else None
        r["files"][n] = hashlib.sha256(text.encode()).hexdigest()
    record["receipt_after"] = json.dumps(r, indent=2) + "\n"
    log = prefix / "state/amendments" / str(time.time_ns())
    op.private(log)
    op.write(log / "transaction.json", json.dumps(record, indent=2))
    for n, text in changes.items():
        atomic(prefix / n, text)
    atomic(prefix / "receipt.json", record["receipt_after"])
    op.write(log / "complete", "complete\n")
    print(
        "Applied validated configuration fields: "
        + ", ".join(sorted(proposal))
        + ". Private rollback record: "
        + str(log)
    )


def rollback(prefix, log):
    if op.owns_process(op.process_record(prefix)):
        raise ValueError("Stop gateway before rollback")
    if not log.resolve().is_relative_to((prefix / "state/amendments").resolve()):
        raise ValueError("Rollback record must belong to prefix")
    r = json.loads((log / "transaction.json").read_text())
    if (prefix / "receipt.json").read_text() not in (
        r["receipt_before"],
        r["receipt_after"],
    ):
        raise ValueError("Receipt changed after amendment")
    for n, after in r["after"].items():
        p = prefix / n
        if p.is_symlink() or (p.read_text() if p.exists() else None) not in (
            r["before"][n],
            after,
        ):
            raise ValueError("Configuration changed after amendment")
    for n, before in r["before"].items():
        p = prefix / n
        if before is None:
            p.unlink(missing_ok=True)
        else:
            atomic(p, before)
    atomic(prefix / "receipt.json", r["receipt_before"])
    print("Restored owned configuration; runtime state preserved.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--prefix", type=Path, default=ROOT / ".local")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--proposal", type=Path)
    g.add_argument("--rollback", type=Path)
    g.add_argument("--observability-env", action="store_true")
    g.add_argument("--disable-observability", action="store_true")
    a = p.parse_args()
    try:
        prefix = a.prefix.absolute()
        if a.proposal:
            configure(prefix, json.loads(a.proposal.read_text()))
        elif a.rollback:
            rollback(prefix, a.rollback.absolute())
        elif a.observability_env:
            configure(
                prefix,
                {
                    "observability": {
                        "enabled": True,
                        "realm": os.environ.get("SPLUNK_REALM"),
                        "access_token": os.environ.get("SPLUNK_ACCESS_TOKEN"),
                    }
                },
            )
        else:
            configure(prefix, {"observability": {"enabled": False}})
    except (ValueError, OSError, KeyError) as e:
        raise SystemExit("REFUSED: " + str(e))

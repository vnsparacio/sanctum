"""Publication checks: report filenames/categories, never secret match contents."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {
    "node_modules",
    ".venv",
    ".ruff_cache",
    ".local",
    "__pycache__",
    "dist",
    ".git",
    "state",
    "logs",
}


def sources(root=ROOT):
    import os

    exclude_finder_metadata = root.resolve() == ROOT.resolve()
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP)
        for n in sorted(
            name
            for name in files
            if name != ".git"
            and not (exclude_finder_metadata and name == ".DS_Store")
        ):
            yield Path(base) / n


PATTERNS = {
    "private_key": (
        r"-----BEGIN (?:(?:RSA|EC|OPENSSH) )?PRIVATE KEY-----"
        r"|-----BEGIN PGP PRIVATE KEY BLOCK-----"
    ),
    "github_token": (
        r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"
    ),
    "linear_token": r"\blin_(?:api|oauth)_[A-Za-z0-9]{20,}\b",
    "provider_key": (
        r"\b(?:sk-[A-Za-z0-9_-]{24,}|AKIA[A-Z0-9]{16}" r"|fc-[A-Za-z0-9_-]{20,})\b"
    ),
    "credential_assignment": (
        r"(?m)^[ \t]*(?:export[ \t]+)?(?:AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN"
        r"|FIRECRAWL_API_KEY|GH_TOKEN|GITHUB_TOKEN|LINEAR_API_KEY|OPENAI_API_KEY"
        r"|PARALLEL_API_KEY|RUNPOD_API_KEY|SPLUNK_ACCESS_TOKEN|SPLUNK_HEC_TOKEN)"
        r"[ \t]*=[ \t]*[\"']?(?!(?i:[^\r\n]*(?:<|\$|\.{3}|configure|example"
        r"|fake|placeholder|synthetic|your)))[A-Za-z0-9_./+=:-]{12,}"
    ),
    "owner_home": r"/Users/(?!example(?:/|$)|<)[a-zA-Z][a-zA-Z0-9_-]+/",
}


def scan(root=ROOT):
    issues = []
    for p in sources(root):
        rel = str(p.relative_to(root))
        if p.is_symlink():
            issues.append((rel, "symlink"))
            continue
        if p.name == ".DS_Store":
            issues.append((rel, "private/generated Finder metadata"))
        if p.name.startswith(".env") and p.name != ".env.example":
            issues.append((rel, "environment file"))
        if p.suffix in {
            ".sqlite",
            ".db",
            ".pem",
            ".key",
            ".gguf",
            ".safetensors",
            ".zip",
            ".gz",
        }:
            issues.append((rel, "private/generated artifact"))
        if p.stat().st_size > 5 * 1024 * 1024:
            issues.append((rel, "large source"))
        text = p.read_text(errors="replace")
        if rel != "scripts/audit.py":
            for label, pattern in PATTERNS.items():
                if re.search(pattern, text):
                    issues.append((rel, label))
    return issues


def docs():
    issues = []
    for p in (path for path in sources() if path.suffix == ".md"):
        for target in re.findall(r"\]\(([^)]+)\)", p.read_text()):
            if (
                "://" not in target
                and not target.startswith("#")
                and not (p.parent / target.split("#")[0]).exists()
            ):
                issues.append((str(p.relative_to(ROOT)), "broken link: " + target))
    return issues


if __name__ == "__main__":
    issues = scan() + docs()
    print(
        json.dumps(
            {"files_scanned": sum(1 for _ in sources()), "issues": issues}, indent=2
        )
    )
    sys.exit(bool(issues))

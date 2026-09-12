#!/usr/bin/env python3
import json
import os
import re
import secrets
import socketserver
import unicodedata
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from pathlib import Path

HOME = Path.home()
CACHE_DIR = Path(os.environ.get("VINCEAI_CACHE_DIR", HOME / ".cache/vinceai"))
SOCKET = CACHE_DIR / "local-markdown.sock"

NOTES_ROOT = Path(os.environ.get("VINCEAI_NOTES_DIR", HOME / "Documents/VinceAI"))
DESTINATIONS = {
    "note": NOTES_ROOT / "Inbox",
    "email_draft": NOTES_ROOT / "Drafts" / "Email",
    "message_draft": NOTES_ROOT / "Drafts" / "Messages",
}

MAX_BODY_BYTES = 24 * 1024
MAX_CONTENT_CHARS = 16 * 1024
MAX_TITLE_CHARS = 120


def send_json(handler, code, payload):
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def safe_directory(path: Path) -> Path:
    NOTES_ROOT.mkdir(parents=True, exist_ok=True)
    if NOTES_ROOT.is_symlink():
        raise RuntimeError("Sanctum root must not be a symlink")

    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError("destination must not be a symlink")

    resolved_root = NOTES_ROOT.resolve()
    resolved_path = path.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise RuntimeError("destination escaped Sanctum root")
    return resolved_path


def slugify(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return (slug[:60].strip("-") or "untitled")


def create_markdown(kind: str, title: str, content: str):
    if kind not in DESTINATIONS:
        raise ValueError("invalid kind")
    if not isinstance(title, str) or not (1 <= len(title.strip()) <= MAX_TITLE_CHARS):
        raise ValueError("invalid title")
    if not isinstance(content, str) or not (1 <= len(content) <= MAX_CONTENT_CHARS):
        raise ValueError("invalid content")
    if "\x00" in title or "\x00" in content:
        raise ValueError("NUL bytes are not allowed")

    target_dir = safe_directory(DESTINATIONS[kind])

    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d-%H%M%S")
    slug = slugify(title.strip())
    suffix = secrets.token_hex(3)
    filename = f"{timestamp}-{slug}-{suffix}.md"
    path = target_dir / filename

    created = datetime.now().astimezone().isoformat(timespec="seconds")
    body = (
        f"<!-- local-ai kind={kind} created={created} -->\n\n"
        f"# {title.strip()}\n\n"
        f"{content.rstrip()}\n"
    )
    encoded = body.encode("utf-8")
    if len(encoded) > 32 * 1024:
        raise ValueError("rendered markdown too large")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    fd = os.open(str(path), flags, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=True) as f:
            f.write(encoded)
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        raise

    relative = path.relative_to(NOTES_ROOT)
    return {
        "ok": True,
        "kind": kind,
        "path": str(path),
        "bytes": len(encoded),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "HybridAILocalMarkdown/1.0"

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        if self.path == "/health":
            return send_json(self, 200, {
                "ok": True,
                "mode": "create-only",
                "root": str(NOTES_ROOT),
            })
        return send_json(self, 404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/save":
            return send_json(self, 404, {"error": "not found"})

        length_raw = self.headers.get("Content-Length", "")
        try:
            length = int(length_raw)
        except ValueError:
            return send_json(self, 400, {"error": "invalid content length"})
        if length < 2 or length > MAX_BODY_BYTES:
            return send_json(self, 413, {"error": "request too large"})

        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            return send_json(self, 400, {"error": "invalid json"})

        if not isinstance(payload, dict) or set(payload.keys()) != {"kind", "title", "content"}:
            return send_json(self, 400, {"error": "invalid request shape"})

        try:
            result = create_markdown(
                payload.get("kind"),
                payload.get("title"),
                payload.get("content"),
            )
        except ValueError as exc:
            return send_json(self, 400, {"error": str(exc)})
        except FileExistsError:
            return send_json(self, 409, {"error": "create collision"})
        except Exception:
            return send_json(self, 500, {"error": "local markdown create failed"})

        return send_json(self, 201, result)

    def do_PUT(self):
        return send_json(self, 405, {"error": "method not allowed"})

    def do_PATCH(self):
        return send_json(self, 405, {"error": "method not allowed"})

    def do_DELETE(self):
        return send_json(self, 405, {"error": "method not allowed"})


class UnixHTTPServer(socketserver.UnixStreamServer):
    allow_reuse_address = False


def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CACHE_DIR, 0o700)

    try:
        SOCKET.unlink()
    except FileNotFoundError:
        pass

    server = UnixHTTPServer(str(SOCKET), Handler)
    os.chmod(SOCKET, 0o600)
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()
        try:
            SOCKET.unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

#!/usr/bin/env python3
import json
import os
import re
import socketserver
import subprocess
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HOME = os.path.expanduser("~")
SOCKET = str(
    Path(os.environ.get("VINCEAI_CACHE_DIR", Path.home() / ".cache/vinceai"))
    / "gmail-read.sock"
)
WRAPPER = str(Path(__file__).with_name("ai-gmail-read"))
MAX_WRAPPER_BYTES = 96 * 1024
MAX_SEARCH_LIMIT = 8
MAX_QUERY = 300
MAX_STRING = 8000

WRAPPED_TEXT = re.compile(
    r'^<<<EXTERNAL_UNTRUSTED_CONTENT id="[^"]+">>>\n'
    r"Source: [^\n]+\n---\n(.*)\n"
    r'<<<END_EXTERNAL_UNTRUSTED_CONTENT id="[^"]+">>>$',
    re.DOTALL,
)


def trim(value, depth=0):
    if depth > 12:
        return "[truncated-depth]"
    if isinstance(value, str):
        return (
            value if len(value) <= MAX_STRING else value[:MAX_STRING] + "\n[truncated]"
        )
    if isinstance(value, list):
        return [trim(v, depth + 1) for v in value[:MAX_SEARCH_LIMIT]]
    if isinstance(value, dict):
        return {str(k): trim(v, depth + 1) for k, v in value.items()}
    return value


def unwrap_search_text(value):
    """Remove gog's verbose per-field wrapper only for compact search metadata.

    The broker retains one explicit top-level untrusted marker for the whole
    search result. Full message reads are NOT unwrapped and keep gog's own
    sanitized/untrusted wrappers intact.
    """
    if not isinstance(value, str):
        return ""
    match = WRAPPED_TEXT.match(value)
    if match:
        return match.group(1).strip()
    return value


def compact_search(parsed):
    if not isinstance(parsed, list):
        return []
    compact = []
    for item in parsed[:MAX_SEARCH_LIMIT]:
        if not isinstance(item, dict):
            continue
        msg_id = item.get("id")
        if not isinstance(msg_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,128}", msg_id
        ):
            continue
        date = item.get("internalDateIso") or item.get("date") or ""
        compact.append(
            {
                "id": msg_id,
                "date": str(date)[:80],
                "from": unwrap_search_text(item.get("from", ""))[:1000],
                "subject": unwrap_search_text(item.get("subject", ""))[:2000],
            }
        )
    return compact


def run_wrapper(args, compact=False):
    try:
        proc = subprocess.run(
            [WRAPPER, *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=20,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 504, {"error": "gmail read timed out"}
    if proc.returncode != 0:
        return 502, {"error": "gmail read failed", "code": proc.returncode}
    if len(proc.stdout) > MAX_WRAPPER_BYTES:
        return 502, {"error": "gmail response exceeded broker limit"}
    try:
        parsed = json.loads(proc.stdout.decode("utf-8"))
    except Exception:
        return 502, {"error": "gmail returned invalid json"}
    data = compact_search(parsed) if compact else trim(parsed)
    return 200, {
        "untrusted": True,
        "source": "gmail",
        "content_is_untrusted": True,
        "data": data,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "HybridAIGmailRead/1.1"

    def log_message(self, fmt, *args):
        return

    def _send(self, code, payload):
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        if parsed.path == "/health":
            return self._send(200, {"ok": True})
        if parsed.path == "/search":
            q = qs.get("q", [""])[0]
            limit_raw = qs.get("limit", ["6"])[0]
            if not q or len(q) > MAX_QUERY:
                return self._send(400, {"error": "invalid query"})
            try:
                limit = int(limit_raw)
            except ValueError:
                return self._send(400, {"error": "invalid limit"})
            if limit < 1 or limit > MAX_SEARCH_LIMIT:
                return self._send(400, {"error": "invalid limit"})
            code, payload = run_wrapper(["search", q, str(limit)], compact=True)
            return self._send(code, payload)
        if parsed.path == "/read":
            msg_id = qs.get("id", [""])[0]
            if (
                not msg_id
                or len(msg_id) > 128
                or not all(c.isalnum() or c in "_-" for c in msg_id)
            ):
                return self._send(400, {"error": "invalid message id"})
            code, payload = run_wrapper(["read", msg_id], compact=False)
            return self._send(code, payload)
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        return self._send(405, {"error": "method not allowed"})

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST


class UnixServer(socketserver.UnixStreamServer):
    allow_reuse_address = False


def main():
    os.makedirs(os.path.dirname(SOCKET), mode=0o700, exist_ok=True)
    if os.path.lexists(SOCKET):
        raise SystemExit("socket exists; lifecycle helper must resolve stale socket")
    try:
        with UnixServer(SOCKET, Handler) as server:
            os.chmod(SOCKET, 0o600)
            server.serve_forever(poll_interval=0.25)
    finally:
        try:
            os.unlink(SOCKET)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

"""Synthetic endpoint/lifecycle only; run the real frozen worker __main__."""

import http.client
import io
import json
import runpy
import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch

package = Path(PACKAGE_ROOT)
fixture = Path(FIXTURE_ROOT)
sys.path[:0] = [str(package), str(package / "src")]
import backends
import lifecycle
from common import Refused


class Interrupted(io.BytesIO):
    def __init__(self, raw, after, error):
        super().__init__(raw)
        self.after = after
        self.count = 0
        self.error = error

    def __next__(self):
        if self.count == self.after:
            errors = {
                "OSError": OSError("INJECTED_PRIVATE_ERROR"),
                "TimeoutError": TimeoutError("INJECTED_PRIVATE_ERROR"),
                "IncompleteRead": http.client.IncompleteRead(b"INJECTED_PRIVATE_BODY"),
                "cancelled": Refused("operation_cancelled"),
                "unrelated": RuntimeError("INJECTED_PRIVATE_ERROR"),
            }
            raise errors[self.error]
        self.count += 1
        return super().__next__()


class SyntheticLifecycle:
    def __init__(self, settings):
        self.settings = settings

    def propose(self, scope, request):
        plan = json.loads((fixture / "plan.json").read_text())
        if plan.get("injectDiagnostic"):
            error = Refused("private_lead_result_schema")
            error.diagnostic = {
                "stage": "JSON_PARSE",
                "validatorVersion": "json/v1",
                "keyword": "syntax",
                "schemaDigest": "d" * 64,
                "semanticSchemaDigest": "e" * 64,
                "INJECTED_PRIVATE_KEY": "INJECTED_PRIVATE_VALUE",
                "error": "INJECTED_PRIVATE_ERROR",
            }
            raise error
        backend = backends.PrivateLeadBackend(self.settings)

        class Opener:
            def open(self, req, timeout=None):
                if req.full_url.endswith("/models"):
                    return io.BytesIO(
                        json.dumps({"data": [{"id": backend.model}]}).encode()
                    )
                if not req.full_url.endswith("/chat/completions"):
                    raise AssertionError("unexpected_endpoint")
                (fixture / "request.json").write_bytes(req.data)
                with (fixture / "dispatches.jsonl").open("a") as out:
                    out.write('{"dispatch":1}\n')
                if plan.get("httpStatus"):
                    raise urllib.error.HTTPError(
                        req.full_url,
                        plan["httpStatus"],
                        "INJECTED_PRIVATE_BODY",
                        {},
                        None,
                    )
                raw = plan.get("wire")
                if raw is None:
                    raw = (
                        "data: "
                        + json.dumps(
                            {
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {"content": plan["text"]},
                                        "finish_reason": plan.get("finish", "stop"),
                                    }
                                ]
                            }
                        )
                        + "\n\n"
                    )
                    if not plan.get("omitDone"):
                        raw += "data: [DONE]\n\n"
                raw = raw.encode()
                if "interruptAfter" in plan:
                    return Interrupted(
                        raw, plan["interruptAfter"], plan.get("error", "OSError")
                    )
                return io.BytesIO(raw)

        with patch("backends.urllib.request.build_opener", return_value=Opener()):
            return backend.propose(request)


lifecycle.PrivateLeadLifecycle = SyntheticLifecycle
runpy.run_path(str(package / "worker.py"), run_name="__main__")

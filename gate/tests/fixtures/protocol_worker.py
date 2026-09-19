"""Offline fixture: real signature/replay, dispatch and streaming backend; no lifecycle."""

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

root = Path(FIXTURE_ROOT)
source = Path(SOURCE_ROOT)
sys.path[:0] = [str(source / "gate"), str(source / "gate/src")]
from authority import authorize
from backends import PrivateLeadBackend
from common import Refused, canonical
from protocol_stream import safe_diagnostic
from worker import execute

settings = json.loads((root / "settings.json").read_text())


class SyntheticLifecycle:
    def propose(self, scope, request):
        # Only the endpoint bytes are scripted. No provider object is constructed.
        backend = PrivateLeadBackend(settings)
        with (
            patch.object(backend, "health_check"),
            patch("backends.urllib.request.build_opener") as opener,
        ):
            opener.return_value.open.return_value = io.BytesIO(
                (root / "stream.txt").read_bytes()
            )
            return backend.propose(request)


try:
    body = authorize(json.load(sys.stdin), settings, settings_hash="a" * 64)
    if body["operation"] != "private_lead_propose":
        raise Refused("fixture_operation")
    print(canonical(execute(body, settings, lifecycle=SyntheticLifecycle())))
except Exception as error:
    result = {
        "status": "UNAVAILABLE",
        "reason": str(error) if type(error) is Refused else "operation_unavailable",
    }
    if type(error) is Refused and hasattr(error, "diagnostic"):
        result["diagnostic"] = safe_diagnostic(error.diagnostic)
    print(canonical(result))
    sys.exit(1)

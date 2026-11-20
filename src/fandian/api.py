"""JSON over HTTP with the standard library."""

import json
import urllib.error
import urllib.parse
import urllib.request


class ApiError(Exception):
    def __init__(self, method: str, url: str, status: int, body: str):
        super().__init__(f"{method} {url} -> {status} {body[:400]}")
        self.status = status
        self.body = body


class Unreachable(Exception):
    """No answer at all: the host does not resolve, refuses the connection or times out."""


def call(method: str, url: str, *, body=None, headers=None, params=None):
    """One JSON request: the decoded body (None when empty), ApiError on a non-2xx, Unreachable
    when no response comes back."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url, data=data, method=method, headers={"Accept": "application/json", **(headers or {})}
    )
    if data is not None:
        request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
    except urllib.error.HTTPError as e:
        raise ApiError(method, url, e.code, e.read().decode(errors="replace")) from None
    except OSError as e:
        reason = getattr(e, "reason", e)
        host = urllib.parse.urlparse(url).hostname
        raise Unreachable(f"Cannot reach {host} ({reason}).") from None

    return json.loads(raw) if raw else None

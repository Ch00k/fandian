"""The tester's mailbox, served against a stand-in for Mailpit's API that answers with messages of
the shape the real one returns (captured from Mailpit v1.34.0). The run's own wiring check
exercises it against a real Mailpit."""

import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from fandian import mailbox

OWN = "new@example.com"


def message(message_id: str, to: str, *, cc: str | None = None) -> dict:
    return {
        "ID": message_id,
        "From": {"Name": "Example", "Address": "webmaster@localhost"},
        "To": [{"Name": "", "Address": to}],
        "Cc": [{"Name": "", "Address": cc}] if cc else [],
        "Bcc": None,
        "ReplyTo": [{"Name": "", "Address": "seller@example.com"}],
        "Subject": f"Hello {to}",
        "Created": "2026-11-20T17:04:17.222Z",
        "Date": "2026-11-20T17:04:17.214Z",
        "Text": "Plain text http://127.0.0.1:8080/x\r\n",
        "HTML": '<p>HTML <a href="http://127.0.0.1:8080/x">link</a></p>\r\n',
        "Attachments": [
            {"PartID": "2", "FileName": "invoice.pdf", "ContentType": "application/pdf", "Size": 13}
        ],
    }


# What Mailpit holds: one message to the tester, one copied to it, and one to an address that
# merely contains the tester's, which Mailpit's `to:` search matches too.
MESSAGES = {
    "own": message("own", OWN),
    "copied": message("copied", "someone@example.com", cc=OWN.upper()),
    "other": message("other", "anew@example.com"),
}


class FakeMailpit(BaseHTTPRequestHandler):
    """Mailpit's search, message and part endpoints, over MESSAGES."""

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        if path == "/api/v1/search":
            summaries = [{**m, "Attachments": len(m["Attachments"])} for m in MESSAGES.values()]
            self._send(json.dumps({"messages": summaries}).encode(), "application/json")
        elif path.startswith("/api/v1/message/") and "/part/" in path:
            self._send(b"%PDF-1.4 test", "application/pdf")
        elif path.startswith("/api/v1/message/") and path.split("/")[-1] in MESSAGES:
            self._send(json.dumps(MESSAGES[path.split("/")[-1]]).encode(), "application/json")
        else:
            self.send_error(404)

    def _send(self, body: bytes, kind: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


def serve(handler: type[BaseHTTPRequestHandler]):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture
def box():
    """The mailbox of OWN, in front of the stand-in, as a function that GETs a path from it."""
    mailpit = serve(FakeMailpit)
    handler = mailbox.handler(OWN, mailbox.Mailpit(f"http://127.0.0.1:{mailpit.server_port}"))
    handler.log_message = lambda *args: None
    server = serve(handler)

    def get(path: str) -> tuple[int, bytes, dict]:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}{path}") as response:
                return response.status, response.read(), dict(response.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)

    yield get
    server.shutdown()
    mailpit.shutdown()


def test_the_inbox_lists_only_mail_sent_to_its_address(box):
    """Including a copy, and leaving out the address Mailpit's search matched by containing it."""
    status, body, _ = box("/api/messages")

    assert status == 200
    assert [m["id"] for m in json.loads(body)] == ["own", "copied"]


def test_the_inbox_page_links_each_message(box):
    status, body, headers = box("/")

    assert status == 200
    assert headers["Content-Type"].startswith("text/html")
    assert b'href="/messages/own"' in body
    assert b'href="/messages/other"' not in body


def test_a_message_comes_whole_with_its_attachments(box):
    status, body, _ = box("/api/messages/own")
    found = json.loads(body)

    assert status == 200
    assert found["to"] == [OWN]
    assert found["reply_to"] == ["seller@example.com"]
    assert found["text"].startswith("Plain text")
    assert found["attachments"] == [
        {
            "name": "invoice.pdf",
            "type": "application/pdf",
            "size": 13,
            "url": "/messages/own/parts/2",
        }
    ]


def test_a_message_page_shows_its_html_and_attachment_links(box):
    status, body, _ = box("/messages/own")

    assert status == 200
    assert b'<a href="http://127.0.0.1:8080/x">link</a>' in body
    assert b'href="/messages/own/parts/2"' in body


def test_an_attachment_downloads_with_its_type_and_name(box):
    status, body, headers = box("/messages/own/parts/2")

    assert status == 200
    assert body == b"%PDF-1.4 test"
    assert headers["Content-Type"] == "application/pdf"
    assert "invoice.pdf" in headers["Content-Disposition"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/messages/other",
        "/messages/other",
        "/messages/other/parts/2",
        "/messages/own/parts/9",
        "/api/messages/missing",
        "/elsewhere",
    ],
)
def test_anything_not_sent_to_the_address_is_not_found(box, path):
    """Another address's mail is as unknown as mail that does not exist."""
    status, body, _ = box(path)

    assert status == 404
    assert b"anew@example.com" not in body


def test_recipients_are_matched_whatever_their_case():
    assert mailbox.addressed_to(MESSAGES["copied"], OWN)
    assert not mailbox.addressed_to(MESSAGES["other"], OWN)

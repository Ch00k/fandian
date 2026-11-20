"""The tester's mailbox: the mail sent to one address, served in front of the run's Mailpit.

Mailpit catches every message the instance sends and shows all of them to whoever asks. The tester
is a user with a mailbox of their own, so this serves only what was sent to its address: a page per
message and its attachments for the browser, and the same as JSON for scripts. A message to anyone
else is as unknown as one that does not exist.

It runs in a container of its own on the run's network, from the tester's image, with the standard
library only: `python3 /opt/mailbox.py`, given ADDRESS, MAILPIT_URL and PORT.
"""

import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Mailpit's search returns this many messages at most per request.
LIMIT = 1000

_MESSAGE = re.compile(r"/(api/)?messages/([A-Za-z0-9]+)")
_PART = re.compile(r"/messages/([A-Za-z0-9]+)/parts/([0-9.]+)")


class NotFound(Exception):
    pass


def recipients(message: dict) -> set[str]:
    """Every address a message went to, in lower case."""
    found = set()
    for field in ("To", "Cc", "Bcc"):
        found |= {recipient["Address"].lower() for recipient in message.get(field) or []}
    return found


def addressed_to(message: dict, address: str) -> bool:
    return address.lower() in recipients(message)


def summary(message: dict) -> dict:
    """A message as the mailbox lists it."""
    return {
        "id": message["ID"],
        "from": message["From"]["Address"],
        "to": sorted(recipients(message)),
        "subject": message["Subject"],
        "date": message["Created"],
        "attachments": message["Attachments"],
    }


def detail(message: dict) -> dict:
    """A whole message, its attachments by the path that downloads each."""
    return {
        "id": message["ID"],
        "from": message["From"]["Address"],
        "to": sorted(recipients(message)),
        "reply_to": [reply["Address"] for reply in message.get("ReplyTo") or []],
        "subject": message["Subject"],
        "date": message["Date"],
        "text": message["Text"],
        "html": message["HTML"],
        "attachments": [
            {
                "name": attachment["FileName"],
                "type": attachment["ContentType"],
                "size": attachment["Size"],
                "url": f"/messages/{message['ID']}/parts/{attachment['PartID']}",
            }
            for attachment in message.get("Attachments") or []
        ],
    }


def render_inbox(address: str, messages: list[dict]) -> str:
    rows = "".join(
        f"<tr><td>{html.escape(m['date'])}</td><td>{html.escape(m['from'])}</td>"
        f'<td><a href="/messages/{m["id"]}">{html.escape(m["subject"] or "(no subject)")}</a></td>'
        f"<td>{m['attachments'] or ''}</td></tr>"
        for m in messages
    )
    body = (
        f"<table><tr><th>Received</th><th>From</th><th>Subject</th><th>Attachments</th></tr>{rows}</table>"
        if messages
        else "<p>No messages.</p>"
    )
    return _page(f"Inbox of {address}", f"<h1>Inbox of {html.escape(address)}</h1>{body}")


def render_message(message: dict) -> str:
    attachments = "".join(
        f'<li><a href="{a["url"]}">{html.escape(a["name"])}</a> '
        f"({html.escape(a['type'])}, {a['size']} bytes)</li>"
        for a in message["attachments"]
    )
    headers = (
        f'<p><a href="/">Inbox</a></p><h1>{html.escape(message["subject"] or "(no subject)")}</h1>'
        f"<p>From: {html.escape(message['from'])}<br>"
        f"To: {html.escape(', '.join(message['to']))}<br>"
        f"Date: {html.escape(message['date'])}</p>"
    )
    if attachments:
        headers += f"<ul>{attachments}</ul>"
    content = message["html"] or f"<pre>{html.escape(message['text'])}</pre>"
    return _page(message["subject"], f"{headers}<hr>{content}")


def _page(title: str, body: str) -> str:
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f"<title>{html.escape(title)}</title></head><body>{body}</body></html>"
    )


class Mailpit:
    """The run's Mailpit, read through its API."""

    def __init__(self, url: str):
        self.url = url.rstrip("/")

    def messages_to(self, address: str) -> list[dict]:
        """Every message sent to the address, the latest first. Mailpit's search also matches an
        address that merely contains this one, so each is checked."""
        query = urllib.parse.urlencode({"query": f"to:{address}", "limit": LIMIT})
        found = self._json(f"/api/v1/search?{query}")["messages"] or []
        return [message for message in found if addressed_to(message, address)]

    def message(self, address: str, message_id: str) -> dict:
        message = self._json(f"/api/v1/message/{message_id}")
        if not addressed_to(message, address):
            raise NotFound(message_id)
        return message

    def part(self, address: str, message_id: str, part_id: str) -> tuple[bytes, str, str]:
        """An attachment's bytes, its type and its file name."""
        message = self.message(address, message_id)
        for attachment in message.get("Attachments") or []:
            if attachment["PartID"] == part_id:
                content = self._get(f"/api/v1/message/{message_id}/part/{part_id}")
                return content, attachment["ContentType"], attachment["FileName"]
        raise NotFound(part_id)

    def _json(self, path: str) -> dict:
        return json.loads(self._get(path))

    def _get(self, path: str) -> bytes:
        try:
            with urllib.request.urlopen(f"{self.url}{path}", timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise NotFound(path) from None
            raise


def handler(address: str, mailpit: Mailpit) -> type[BaseHTTPRequestHandler]:
    class Mailbox(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - the name http.server calls
            path = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
            try:
                self._route(path)
            except NotFound:
                self._send(404, b"Not found", "text/plain")

        def _route(self, path: str) -> None:
            if path == "/":
                messages = [summary(m) for m in mailpit.messages_to(address)]
                self._send(
                    200, render_inbox(address, messages).encode(), "text/html; charset=utf-8"
                )
            elif path == "/api/messages":
                messages = [summary(m) for m in mailpit.messages_to(address)]
                self._send(200, json.dumps(messages).encode(), "application/json")
            elif match := _PART.fullmatch(path):
                content, kind, name = mailpit.part(address, *match.groups())
                disposition = f"inline; filename*=UTF-8''{urllib.parse.quote(name)}"
                self._send(200, content, kind, {"Content-Disposition": disposition})
            elif match := _MESSAGE.fullmatch(path):
                api, message_id = match.groups()
                message = detail(mailpit.message(address, message_id))
                if api:
                    self._send(200, json.dumps(message).encode(), "application/json")
                else:
                    self._send(200, render_message(message).encode(), "text/html; charset=utf-8")
            else:
                raise NotFound(path)

        def _send(self, status: int, body: bytes, kind: str, headers: dict | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

    return Mailbox


def main() -> None:
    address = os.environ["ADDRESS"]
    mailpit = Mailpit(os.environ["MAILPIT_URL"])
    server = ThreadingHTTPServer(
        ("", int(os.environ.get("PORT", "8000"))), handler(address, mailpit)
    )
    server.serve_forever()


if __name__ == "__main__":
    main()

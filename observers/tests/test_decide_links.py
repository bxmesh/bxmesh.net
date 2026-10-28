"""The one-time Approve and Decline links in the new-application email, and the console's
buttons that share their code. Run from the repo root: pytest observers/tests

No network, broker, mail server or Cloudflare: Access, EMQX and SMTP are stubbed, and each test
has its own SQLite file.
"""

import hashlib
import importlib
import os
import re
import sqlite3
import sys
import tempfile
import threading
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="observers-test-"))
os.environ["PUBLIC_URL"] = "https://bxmesh.example"
with mock.patch.object(threading.Thread, "start"):  # not the EMQX poller
    app_module = importlib.import_module("app")

REAL_ADMIN_EMAIL = app_module.admin_email
ADMIN = "admin@example.com"
ORIGIN = {"Origin": "https://bxmesh.example"}
LINK = re.compile(r"^(Approve|Decline): https://bxmesh\.example(/admin/decide/[A-Za-z0-9_-]+)$", re.M)


class Response:
    def __init__(self, status_code, text=""):
        self.status_code, self.text = status_code, text


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A fresh database, a signed-in admin, and a record of the broker calls and mail."""
    monkeypatch.setattr(app_module, "DB", tmp_path / "observers.db")
    app_module.init_db()
    monkeypatch.setenv("NOTIFY_TO", "owner@example.com")
    monkeypatch.setenv("TURNSTILE_SITEKEY", "")
    monkeypatch.setenv("MAIL_FROM", "BXMesh observers <observers@bxmesh.example>")
    monkeypatch.setenv("DISCORD_URL", "https://discord.example/invite")
    monkeypatch.setattr(app_module, "admin_email", lambda: ADMIN)
    calls = {"emqx": [], "mail": []}
    monkeypatch.setattr(app_module, "emqx", lambda m, p, b=None: calls["emqx"].append((m, p, b)) or Response(201))
    monkeypatch.setattr(app_module, "send_mail", lambda to, subject, text: calls["mail"].append((to, subject, text)))
    app_module.app.config["TESTING"] = True
    return calls


@pytest.fixture
def client(env):
    return app_module.app.test_client()


def apply(client, env, username="newnode"):
    """Applies through /join; returns the application's id and its email's links by action."""
    r = client.post("/join", data={"location": "Orange", "username": username, "node_type": "meshcoretomqtt",
                                   "node_name": "Orange Hill", "email": f"{username}@example.com", "notes": "hi"})
    assert r.status_code == 200
    to, subject, text = env["mail"][-1]
    assert to == "owner@example.com" and subject == f"New observer application: {username}"
    links = {m[1]: m[2] for m in LINK.finditer(text)}
    assert set(links) == {"Approve", "Decline"}
    assert "https://bxmesh.example/admin\n" in text  # the console link is still there
    with app_module.db() as c:
        app_id = c.execute("SELECT id FROM applications WHERE username = ?", (username,)).fetchone()[0]
    return app_id, links


def status(app_id):
    with app_module.db() as c:
        return c.execute("SELECT status, decided_by FROM applications WHERE id = ?", (app_id,)).fetchone()


def test_only_hashes_are_stored(client, env):
    app_id, links = apply(client, env)
    raw = Path(app_module.DB).read_bytes()
    with app_module.db() as c:
        rows = c.execute("SELECT * FROM decision_tokens WHERE app_id = ?", (app_id,)).fetchall()
    assert {r["action"] for r in rows} == {"approve", "reject"}
    for link in links.values():
        token = link.rsplit("/", 1)[1]
        assert len(token) >= 43  # token_urlsafe(32)
        assert token.encode() not in raw
        assert hashlib.sha256(token.encode()).hexdigest() in {r["hash"] for r in rows}
    # Approve and Decline links are different tokens.
    assert links["Approve"] != links["Decline"]


def test_get_never_acts(client, env):
    app_id, links = apply(client, env)
    for _ in range(3):  # a scanner, a preview, the owner
        r = client.get(links["Approve"])
        assert r.status_code == 200
        assert b"Approve newnode?" in r.data and b"Approve and email" in r.data
        r = client.get(links["Decline"])
        assert r.status_code == 200 and b"Decline newnode?" in r.data
    assert status(app_id)["status"] == "pending"
    assert env["emqx"] == [] and len(env["mail"]) == 1


def test_approve_link_acts_once(client, env):
    app_id, links = apply(client, env)
    r = client.post(links["Approve"], headers=ORIGIN)
    assert r.status_code == 302 and "Approved%20newnode" in r.headers["Location"]
    assert status(app_id)["status"] == "approved" and status(app_id)["decided_by"] == ADMIN
    assert [c[0] for c in env["emqx"]] == ["POST"]
    assert env["mail"][-1][0] == "newnode@example.com"  # the credentials
    # Used up: again, or the other action.
    for link in links.values():
        r = client.post(link, headers=ORIGIN)
        assert r.status_code == 409 and b"Already decided" in r.data
        r = client.get(link)
        assert b"Already decided" in r.data and b"newnode was approved by admin@example.com" in r.data
    assert len(env["emqx"]) == 1


def assert_declined_mail(mail, username="newnode"):
    to, subject, text = mail
    assert to == f"{username}@example.com" and subject == "Your BXMesh observer application"
    assert text.startswith("G'day,") and text.rstrip().endswith("BXMesh")
    assert "chosen not to admit your application" in text
    assert "https://discord.example/invite" in text and "observers@bxmesh.example" in text


def test_decline_link_rejects_and_emails_the_applicant(client, env):
    app_id, links = apply(client, env)
    mails = len(env["mail"])
    r = client.post(links["Decline"], headers=ORIGIN)
    assert r.status_code == 302 and "Rejected%20newnode" in r.headers["Location"]
    assert status(app_id)["status"] == "rejected"
    assert len(env["mail"]) == mails + 1 and env["emqx"] == []
    assert_declined_mail(env["mail"][-1])
    r = client.post(links["Approve"], headers=ORIGIN)
    assert r.status_code == 409 and status(app_id)["status"] == "rejected"
    assert len(env["mail"]) == mails + 1


def test_decline_stands_when_its_email_fails(client, env, monkeypatch):
    app_id, links = apply(client, env)

    def fail(to, subject, text):
        raise OSError("smtp down")
    monkeypatch.setattr(app_module, "send_mail", fail)
    r = client.post(links["Decline"], headers=ORIGIN)
    assert r.status_code == 302
    assert "haven%27t%20been%20told" in r.headers["Location"] and "smtp%20down" in r.headers["Location"]
    assert status(app_id)["status"] == "rejected"
    assert client.post(links["Decline"], headers=ORIGIN).status_code == 409


def test_expired_link_does_nothing(client, env):
    app_id, links = apply(client, env)
    with app_module.db() as c:
        c.execute("UPDATE decision_tokens SET expires = created - 1 WHERE app_id = ?", (app_id,))
    r = client.get(links["Approve"])
    assert r.status_code == 200 and b"This link has expired" in r.data and b"admin console" in r.data
    assert b"Approve and email" not in r.data
    r = client.post(links["Approve"], headers=ORIGIN)
    assert r.status_code == 409
    assert status(app_id)["status"] == "pending" and env["emqx"] == []


def test_expiry_setting(client, env, monkeypatch):
    monkeypatch.setattr(app_module, "DECISION_LINK_DAYS", 2)
    app_id, _ = apply(client, env)
    with app_module.db() as c:
        row = c.execute("SELECT created, expires FROM decision_tokens WHERE app_id = ?", (app_id,)).fetchone()
    assert row["expires"] - row["created"] == pytest.approx(2 * 86400)
    assert "lasts 2 days" in env["mail"][-1][2]


def test_console_approve_uses_up_the_links(client, env):
    app_id, links = apply(client, env)
    r = client.post(f"/admin/{app_id}/approve", headers=ORIGIN)
    assert r.status_code == 302 and "Approved%20newnode" in r.headers["Location"]
    assert status(app_id)["status"] == "approved"
    with app_module.db() as c:
        assert c.execute("SELECT COUNT(*) FROM decision_tokens WHERE app_id = ? AND used IS NULL",
                         (app_id,)).fetchone()[0] == 0
    r = client.get(links["Decline"])
    assert b"newnode was approved by admin@example.com" in r.data
    r = client.post(links["Decline"], headers=ORIGIN)
    assert r.status_code == 409 and status(app_id)["status"] == "approved"


def test_console_reject_uses_up_the_links(client, env):
    app_id, links = apply(client, env)
    mails = len(env["mail"])
    r = client.post(f"/admin/{app_id}/reject", headers=ORIGIN)
    assert r.status_code == 302 and "Rejected%20newnode" in r.headers["Location"]
    assert status(app_id)["status"] == "rejected"
    assert len(env["mail"]) == mails + 1
    assert_declined_mail(env["mail"][-1])
    r = client.post(links["Approve"], headers=ORIGIN)
    assert r.status_code == 409 and env["emqx"] == []


def test_console_approve_failure_keeps_the_links(client, env, monkeypatch):
    """The broker refusing records nothing, so the links still work."""
    app_id, links = apply(client, env)
    monkeypatch.setattr(app_module, "emqx", lambda m, p, b=None: Response(400, "nope"))
    r = client.post(f"/admin/{app_id}/approve", headers=ORIGIN)
    assert "refused" in r.headers["Location"] and status(app_id)["status"] == "pending"
    assert b"Approve newnode?" in client.get(links["Approve"]).data


def test_post_needs_same_origin(client, env):
    app_id, links = apply(client, env)
    assert client.post(links["Approve"]).status_code == 403
    assert client.post(links["Approve"], headers={"Origin": "https://evil.example"}).status_code == 403
    assert status(app_id)["status"] == "pending"


def test_links_need_access(client, env, monkeypatch):
    """The real Access check: no token, no page and no action."""
    monkeypatch.setattr(app_module, "admin_email", REAL_ADMIN_EMAIL)
    app_id, links = apply(client, env)
    assert client.get(links["Approve"]).status_code == 403
    assert client.post(links["Approve"], headers=ORIGIN).status_code == 403
    assert status(app_id)["status"] == "pending"


def test_unknown_token(client, env):
    assert client.get("/admin/decide/not-a-token").status_code == 404
    assert client.post("/admin/decide/not-a-token", headers=ORIGIN).status_code == 404


def test_migration_on_an_existing_database(tmp_path, monkeypatch):
    """An observers.db from before this change keeps its rows and gains the table; twice is fine."""
    db = tmp_path / "observers.db"
    with sqlite3.connect(db) as c:
        c.execute("""CREATE TABLE applications (
            id INTEGER PRIMARY KEY, created REAL, username TEXT, email TEXT, location TEXT,
            node_type TEXT, node_name TEXT, public_key TEXT, notes TEXT, ip TEXT,
            status TEXT DEFAULT 'pending', decided REAL, decided_by TEXT)""")
        c.execute("INSERT INTO applications (username, status) VALUES ('old', 'approved')")
    monkeypatch.setattr(app_module, "DB", db)
    app_module.init_db()
    app_module.init_db()
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT username, status FROM applications").fetchall() == [("old", "approved")]
        assert c.execute("SELECT COUNT(*) FROM decision_tokens").fetchone()[0] == 0


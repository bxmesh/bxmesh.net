"""bxmesh.net/join: apply for an MQTT login; bxmesh.net/admin: the approvals page.

The gateway sends bxmesh.net's /join and /admin paths here (everything else is
the static site), so every route this app serves is under one of the two.

Public, /join: a form (location, username, the node feeding data, email), guarded by
Cloudflare Turnstile, a honeypot field and per-address rate limits.

/admin (behind Cloudflare Access; the Access token is verified here too):
pending applications to approve or reject; every login with whether it's
connected now, from where, when it was last seen and how many messages it
sent in the last hour; revoke, which deletes the login on the broker and
drops its live connection at once.

Approving creates the login on EMQX (REST API) with a generated password and
emails it, with the endpoint, topic layout and config for openHop and
meshcoretomqtt. One connection per login is enforced by the broker itself
(mqtt.clientid_override = username).

A background thread polls EMQX every POLL_SECONDS for each login's connection.
State is one SQLite file on its own volume; the app runs as a single pod.
"""

import logging
import os
import re
import secrets
import smtplib
import sqlite3
import ssl
import string
import threading
import time
import urllib.parse
from email.message import EmailMessage
from pathlib import Path

import jwt
import requests
from flask import Flask, abort, redirect, render_template, request

log = logging.getLogger("observers")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

E = os.environ
DB = Path(E.get("DATA_DIR", "/srv/data")) / "observers.db"
SECRETS = Path("/srv/secrets")
EMQX_API = E.get("EMQX_API", "http://emqx.dmz-corescope.svc.cluster.local:18083")
USERS = "/api/v5/authentication/password_based%3Abuilt_in_database/users"
PUBLIC_URL = E.get("PUBLIC_URL", "https://bxmesh.net")
ADMIN_EMAILS = {e.strip().lower() for e in E.get("ADMIN_EMAILS", "").split(",") if e.strip()}
SYSTEM_USERS = {"corescope"}
POLL_SECONDS = 60
USERNAME = re.compile(r"^[a-z0-9][a-z0-9_-]{2,31}$")
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[a-z]{2,}$", re.I)
PUBKEY = re.compile(r"^[0-9a-fA-F]{6,64}$")
NODE_TYPES = ["openHop (pyMC Repeater)", "meshcoretomqtt", "Observer firmware (ESP32)", "Other"]

app = Flask(__name__)


def secret(name: str) -> str:
    return (SECRETS / name).read_text().strip()


def setting(name: str) -> str:
    return E.get(name, "")


# --- database -----------------------------------------------------------------

def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    with db() as c:
        c.executescript("""
        PRAGMA journal_mode = DELETE;  -- CephFS: no WAL shared-memory file
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY, created REAL, username TEXT, email TEXT, location TEXT,
            node_type TEXT, node_name TEXT, public_key TEXT, notes TEXT, ip TEXT,
            status TEXT DEFAULT 'pending', decided REAL, decided_by TEXT);
        CREATE TABLE IF NOT EXISTS usage (
            username TEXT PRIMARY KEY, connected INTEGER, connected_at TEXT, ip TEXT,
            last_seen REAL, recv_prev INTEGER, connected_at_prev TEXT);
        CREATE TABLE IF NOT EXISTS samples (username TEXT, ts REAL, msgs INTEGER);
        CREATE TABLE IF NOT EXISTS hits (ip TEXT, ts REAL);
        """)


# --- broker -------------------------------------------------------------------

def emqx(method: str, path: str, body: dict | None = None) -> requests.Response:
    key, _, sec = secret("emqx_api_key").partition(":")
    return requests.request(method, EMQX_API + path, json=body, auth=(key, sec), timeout=15)


def new_password() -> str:
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))


def poll_forever() -> None:
    """Every POLL_SECONDS: each login's connection, IP, last seen, and the
    messages it sent since the last poll (from EMQX's recv_msg counter)."""
    while True:
        try:
            poll()
        except Exception:
            log.exception("polling EMQX failed")
        time.sleep(POLL_SECONDS)


def poll() -> None:
    r = emqx("GET", "/api/v5/clients?limit=1000")
    r.raise_for_status()
    live = {c["username"]: c for c in r.json().get("data", []) if c.get("username") and c.get("connected")}
    now = time.time()
    with db() as c:
        approved = [row["username"] for row in c.execute("SELECT username FROM applications WHERE status = 'approved'")]
        for user in approved:
            cl = live.get(user)
            prev = c.execute("SELECT * FROM usage WHERE username = ?", (user,)).fetchone()
            if cl:
                recv = int(cl.get("recv_msg") or 0)
                same = prev and prev["connected_at_prev"] == cl.get("connected_at")
                delta = recv - (prev["recv_prev"] or 0) if same else recv
                c.execute("INSERT INTO samples VALUES (?, ?, ?)", (user, now, max(0, delta)))
                c.execute("INSERT OR REPLACE INTO usage VALUES (?, 1, ?, ?, ?, ?, ?)",
                          (user, cl.get("connected_at"), cl.get("ip_address"), now, recv, cl.get("connected_at")))
            elif prev:
                c.execute("UPDATE usage SET connected = 0 WHERE username = ?", (user,))
        c.execute("DELETE FROM samples WHERE ts < ?", (now - 7200,))
        c.execute("DELETE FROM hits WHERE ts < ?", (now - 86400,))


# --- mail ---------------------------------------------------------------------

def send_mail(to: str, subject: str, text: str) -> None:
    """Plain text only: Gmail dropped the HTML version of the login email from this
    new domain, while the same text alone arrives in the inbox."""
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = setting("MAIL_FROM"), to, subject
    if setting("REPLY_TO"):
        msg["Reply-To"] = setting("REPLY_TO")
    msg.set_content(text)
    with smtplib.SMTP_SSL(setting("SMTP_HOST"), int(setting("SMTP_PORT") or 465),
                          context=ssl.create_default_context(), timeout=30) as s:
        s.login(setting("SMTP_USER"), secret("smtp_password"))
        s.send_message(msg)


def credentials_mail(app_row: sqlite3.Row, password: str) -> str:
    return render_template("credentials.txt", a=app_row, password=password, host=setting("MQTT_PUBLIC_HOST"),
                           corescope=setting("CORESCOPE_URL"), discord=setting("DISCORD_URL"),
                           setup=setting("SETUP_URL"))


# --- guards -------------------------------------------------------------------

_jwks = None


def admin_email() -> str:
    """The signed-in admin, from Cloudflare Access's token (verified, not trusted)."""
    global _jwks
    token = request.headers.get("Cf-Access-Jwt-Assertion") or request.cookies.get("CF_Authorization")
    if not token:
        abort(403)
    team = setting("ACCESS_TEAM")
    if _jwks is None:
        _jwks = jwt.PyJWKClient(f"https://{team}/cdn-cgi/access/certs", cache_keys=True, lifespan=3600)
    try:
        key = _jwks.get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=["RS256"], audience=setting("ACCESS_AUD"),
                            issuer=f"https://{team}")
    except jwt.PyJWTError as err:
        log.warning("rejected an Access token: %s", err)
        abort(403)
    email = (claims.get("email") or "").lower()
    if email not in ADMIN_EMAILS:
        abort(403)
    return email


def same_origin() -> None:
    """Admin actions only from the admin page itself (no cross-site POSTs)."""
    if urllib.parse.urlparse(request.headers.get("Origin", "")).netloc != urllib.parse.urlparse(PUBLIC_URL).netloc:
        abort(403)


def client_ip() -> str:
    return request.headers.get("Cf-Connecting-Ip") or request.remote_addr or "?"


def turnstile_ok(token: str) -> bool:
    if not setting("TURNSTILE_SITEKEY"):
        return True  # not configured (local testing)
    r = requests.post("https://challenges.cloudflare.com/turnstile/v0/siteverify", timeout=10,
                      data={"secret": secret("turnstile_secret"), "response": token, "remoteip": client_ip()})
    return bool(r.ok and r.json().get("success"))


# --- public pages ---------------------------------------------------------------

def page_vars(**extra) -> dict:
    return {"sitekey": setting("TURNSTILE_SITEKEY"), "node_types": NODE_TYPES, "corescope": setting("CORESCOPE_URL"),
            "discord": setting("DISCORD_URL"), "host": setting("MQTT_PUBLIC_HOST"), **extra}


@app.get("/join")
def form():
    return render_template("apply.html", **page_vars(values={}, errors=[]))


@app.post("/join")
def apply():
    f = {k: (request.form.get(k) or "").strip() for k in
         ("location", "username", "node_type", "node_name", "public_key", "email", "notes")}
    f["username"] = f["username"].lower()
    if request.form.get("website"):  # the honeypot: a field people never see
        return render_template("thanks.html", **page_vars())
    errors = []
    ip, now = client_ip(), time.time()
    with db() as c:
        if c.execute("SELECT COUNT(*) FROM hits WHERE ip = ? AND ts > ?", (ip, now - 3600)).fetchone()[0] >= 5:
            errors.append("Too many applications from your address in the last hour. Try again later.")
        if c.execute("SELECT COUNT(*) FROM hits WHERE ts > ?", (now - 86400,)).fetchone()[0] >= 100:
            errors.append("We're taking a break from new applications today. Try again tomorrow.")
        c.execute("INSERT INTO hits VALUES (?, ?)", (ip, now))
    if not errors and not turnstile_ok(request.form.get("cf-turnstile-response", "")):
        errors.append("The check that you're a person didn't pass. Reload the page and try again.")
    if not f["location"]:
        errors.append("Tell us where you are, roughly: a town or suburb is enough.")
    if not USERNAME.match(f["username"]) or f["username"] in SYSTEM_USERS:
        errors.append("Usernames are 3 to 32 characters: lowercase letters, numbers, - and _, starting with a letter or number.")
    if f["node_type"] not in NODE_TYPES:
        errors.append("Pick what's feeding the data.")
    if not f["node_name"]:
        errors.append("Give your node's name, as it advertises on the mesh.")
    if f["public_key"] and not PUBKEY.match(f["public_key"]):
        errors.append("The public key is hexadecimal: 0-9 and a-f.")
    if not EMAIL.match(f["email"]):
        errors.append("That email address doesn't look right.")
    if not errors:
        with db() as c:
            taken = c.execute("SELECT 1 FROM applications WHERE username = ? AND status IN ('pending', 'approved')",
                              (f["username"],)).fetchone()
        if taken:
            errors.append("That username is taken or already applied for. Pick another.")
    if errors:
        return render_template("apply.html", **page_vars(values=f, errors=errors)), 400
    with db() as c:
        c.execute("INSERT INTO applications (created, username, email, location, node_type, node_name, public_key, notes, ip) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (now, f["username"], f["email"], f["location"], f["node_type"], f["node_name"],
                   f["public_key"], f["notes"][:1000], ip))
    if setting("NOTIFY_TO"):
        try:
            send_mail(setting("NOTIFY_TO"), f"New observer application: {f['username']}",
                      f"{f['username']} ({f['email']}) applied for an MQTT login.\n\n"
                      f"Location: {f['location']}\nNode: {f['node_name']} ({f['node_type']})\n"
                      f"Public key: {f['public_key'] or '-'}\nNotes: {f['notes'] or '-'}\n\n"
                      f"Approve or reject it at {PUBLIC_URL}/admin\n")
        except Exception:
            log.exception("couldn't send the new-application notice")
    return render_template("thanks.html", **page_vars())


@app.get("/healthz")
def healthz():
    with db() as c:
        c.execute("SELECT 1")
    return "ok"


# --- admin ----------------------------------------------------------------------

def ago(ts: float | None) -> str:
    if not ts:
        return "never"
    s = int(time.time() - ts)
    for unit, n in (("d", 86400), ("h", 3600), ("min", 60)):
        if s >= n:
            return f"{s // n} {unit} ago"
    return "just now"


@app.get("/admin")
def admin():
    who = admin_email()
    now = time.time()
    with db() as c:
        pending = c.execute("SELECT * FROM applications WHERE status = 'pending' ORDER BY created").fetchall()
        logins = c.execute("""
            SELECT a.*, u.connected, u.connected_at, u.ip, u.last_seen,
                   (SELECT COALESCE(SUM(msgs), 0) FROM samples s WHERE s.username = a.username AND s.ts > ?) AS hour
            FROM applications a LEFT JOIN usage u ON u.username = a.username
            WHERE a.status = 'approved' ORDER BY a.username""", (now - 3600,)).fetchall()
        history = c.execute("SELECT * FROM applications WHERE status IN ('rejected', 'revoked') "
                            "ORDER BY decided DESC LIMIT 50").fetchall()
    return render_template("admin.html", who=who, pending=pending, logins=logins, history=history, ago=ago,
                           flash=request.args.get("msg", ""), corescope=setting("CORESCOPE_URL"))


def decide(app_id: int, status: str, who: str) -> None:
    with db() as c:
        c.execute("UPDATE applications SET status = ?, decided = ?, decided_by = ? WHERE id = ?",
                  (status, time.time(), who, app_id))


@app.post("/admin/<int:app_id>/approve")
def approve(app_id: int):
    who = admin_email()
    same_origin()
    with db() as c:
        a = c.execute("SELECT * FROM applications WHERE id = ? AND status = 'pending'", (app_id,)).fetchone()
    if not a:
        return redirect("/admin?msg=" + urllib.parse.quote("That application isn't pending any more."))
    password = new_password()
    r = emqx("POST", USERS, {"user_id": a["username"], "password": password, "is_superuser": False})
    if r.status_code not in (200, 201):
        return redirect("/admin?msg=" + urllib.parse.quote(f"The broker refused to create {a['username']}: {r.text[:200]}"))
    try:
        send_mail(a["email"], "Your BXMesh MQTT login", credentials_mail(a, password))
    except Exception as err:
        emqx("DELETE", f"{USERS}/{a['username']}")  # no login without its email
        log.exception("credentials email failed")
        return redirect("/admin?msg=" + urllib.parse.quote(f"Couldn't email {a['email']} ({err}); nothing was created."))
    decide(app_id, "approved", who)
    return redirect("/admin?msg=" + urllib.parse.quote(f"Approved {a['username']}; their login is on its way to {a['email']}."))


@app.post("/admin/<int:app_id>/reject")
def reject(app_id: int):
    who = admin_email()
    same_origin()
    decide(app_id, "rejected", who)
    return redirect("/admin?msg=" + urllib.parse.quote("Rejected."))


@app.post("/admin/<int:app_id>/revoke")
def revoke(app_id: int):
    who = admin_email()
    same_origin()
    with db() as c:
        a = c.execute("SELECT * FROM applications WHERE id = ? AND status = 'approved'", (app_id,)).fetchone()
    if not a:
        abort(404)
    r = emqx("DELETE", f"{USERS}/{a['username']}")
    if r.status_code not in (200, 204, 404):
        return redirect("/admin?msg=" + urllib.parse.quote(f"The broker refused: {r.text[:200]}"))
    emqx("DELETE", f"/api/v5/clients/{urllib.parse.quote(a['username'], safe='')}")  # client ID = username
    decide(app_id, "revoked", who)
    return redirect("/admin?msg=" + urllib.parse.quote(f"Revoked {a['username']} and dropped its connection."))


init_db()
threading.Thread(target=poll_forever, daemon=True, name="poller").start()

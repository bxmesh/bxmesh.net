"""gunicorn's access log never holds an email link's token (gunicorn.conf.py)."""

import datetime
import importlib.util
import logging
from pathlib import Path
from types import SimpleNamespace

from gunicorn.config import Config

spec = importlib.util.spec_from_file_location("gunicorn_conf", Path(__file__).resolve().parents[1] / "gunicorn.conf.py")
conf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(conf)

TOKEN = "rH-2teTeWY4FvOv4ahykkESCkfzPpcKnYmeVSqmrFbU"


def logged_line(path, referer="-"):
    cfg = Config()
    cfg.set("accesslog", "-")
    log = conf.RedactingLogger(cfg)
    lines = []
    handler = logging.Handler()
    handler.emit = lambda record: lines.append(record.getMessage())
    log.access_log.addHandler(handler)
    req = SimpleNamespace(headers=[("REFERER", referer), ("USER-AGENT", "test")])
    resp = SimpleNamespace(status="200 OK", response_length=1, sent=1, headers=[])
    environ = {"REQUEST_METHOD": "POST", "RAW_URI": path, "PATH_INFO": path.split("?")[0], "QUERY_STRING": "",
               "SERVER_PROTOCOL": "HTTP/1.1", "REMOTE_ADDR": "127.0.0.1", "HTTP_REFERER": referer}
    log.access(resp, req, environ, datetime.timedelta(seconds=0.01))
    assert len(lines) == 1
    return lines[0]


def test_the_token_is_redacted():
    line = logged_line(f"/admin/decide/{TOKEN}", referer=f"https://bxmesh.net/admin/decide/{TOKEN}")
    assert TOKEN not in line
    assert line.count("/admin/decide/[redacted]") == 2


def test_other_paths_are_untouched():
    line = logged_line("/admin/12/approve?msg=x")
    assert "/admin/12/approve?msg=x" in line


def test_the_image_uses_it():
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()
    assert "gunicorn.conf.py" in dockerfile.split("COPY app.py", 1)[1].splitlines()[0]
    assert '"--config", "gunicorn.conf.py"' in dockerfile

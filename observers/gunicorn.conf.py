"""gunicorn's settings beyond the command line: the access log, with the email links' tokens
taken out. A token is a one-time key to approve or decline an application, so it never goes in a
log, from the request line or from the Referer of the confirm page's own POST."""

import re

from gunicorn.glogging import Logger

DECIDE_TOKEN = re.compile(r"(/admin/decide/)[^\s?#\"/]+")


class RedactingLogger(Logger):
    def atoms(self, resp, req, environ, request_time):
        atoms = super().atoms(resp, req, environ, request_time)
        return {k: DECIDE_TOKEN.sub(r"\1[redacted]", v) if isinstance(v, str) else v for k, v in atoms.items()}


logger_class = RedactingLogger

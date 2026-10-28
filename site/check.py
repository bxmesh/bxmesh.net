"""Checks the built site image as it serves: every page's local links and assets load, every
#fragment they point to exists on its page, and no @PLACEHOLDER@ is left. Stdlib only.

    python3 site/check.py http://127.0.0.1:8080

The paths the gateway sends to the observers app (/join, /admin) aren't the site's, so they're
not fetched. Links to other sites aren't checked: that would make the check depend on them.
"""

import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

PAGES = ["/", "/connect/"]
OBSERVERS = ("/join", "/admin")


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.refs.append(value)
            if name == "id" and value:
                self.ids.add(value)


def fetch(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        return err.code, ""


def main(base):
    problems, parsed = [], {}

    def page(path):
        if path not in parsed:
            status, body = fetch(base, path)
            p = Page()
            p.feed(body)
            parsed[path] = (status, body, p)
        return parsed[path]

    for path in PAGES:
        status, body, p = page(path)
        if status != 200:
            problems.append(f"{path}: {status}")
            continue
        if re.search(r"@[A-Z_]+@", body):
            problems.append(f"{path}: a @PLACEHOLDER@ is left")
        refs = p.refs + re.findall(r"url\('?([^')]+)'?\)", body)
        for ref in refs:
            url = urllib.parse.urlsplit(urllib.parse.urljoin(path, ref))
            if url.scheme not in ("", "http", "https") or (url.netloc and ref.startswith(("http:", "https:", "//"))):
                continue  # another site, mailto: and the like
            if url.path.startswith(OBSERVERS):
                continue
            if url.path.endswith(".css"):
                status, css, _ = page(url.path)
                refs.extend(re.findall(r"url\('?([^')]+)'?\)", css))
            target_status, _, target = page(url.path)
            if target_status != 200:
                problems.append(f"{path}: {ref} is {target_status}")
            elif url.fragment and url.fragment not in target.ids:
                problems.append(f"{path}: {ref} has no id {url.fragment!r} on {url.path}")
    for problem in problems:
        print("FAIL", problem)
    print(f"checked {len(parsed)} paths from {len(PAGES)} pages: {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1].rstrip("/")))

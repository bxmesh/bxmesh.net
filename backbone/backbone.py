"""BxMesh's backbone: the eight repeaters the network uses the most, for /repeaters/.

Runs beside nginx in each site pod. Every INTERVAL seconds it reads CoreScope's public API,
ranks the region's repeaters and writes the cards as an HTML fragment to OUT, which nginx
includes into the page as it serves it (site/nginx.conf, server-side includes). So a visitor
never waits on CoreScope, and the page needs no JavaScript. If a fetch fails the last fragment
stays; until the first one, the page shows its own fallback list.

The ranking is CoreScope's usefulness score: its weighted mix of how much of the mesh a
repeater links up (bridge, coverage, redundancy, from the neighbour graph) and the traffic it
relays. Only repeaters placed in the region, and heard in the last day, count.
"""

import html
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

CORESCOPE = os.environ.get("CORESCOPE_URL", "https://corescope.bxmesh.net").rstrip("/")
REGION = os.environ.get("REGION", "BHS")
COUNT = int(os.environ.get("COUNT", "8"))
INTERVAL = int(os.environ.get("INTERVAL", "600"))
OUT = os.environ.get("OUT", "/data/backbone.html")
HEARD_WITHIN = timedelta(days=1)
# Owners' names often end in "Rptr" or "Repeater"; on a page of repeaters it's noise.
SUFFIXES = (" rptr", " repeater")


def get(path):
    req = urllib.request.Request(CORESCOPE + path, headers={"User-Agent": "bxmesh.net-backbone/1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def short_name(name):
    name = " ".join(name.split())
    for suffix in SUFFIXES:
        if name.lower().endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)]
    return name


def rank(nodes, neighbours, now):
    """The top COUNT repeaters in REGION, heard within HEARD_WITHIN, by usefulness."""
    picked = []
    for n in nodes:
        regions = (n.get("region_placement") or {}).get("regions") or []
        if n.get("role") != "repeater" or n.get("foreign") or REGION not in regions:
            continue
        try:
            heard = datetime.fromisoformat(n["last_seen"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError):
            continue
        if now - heard > HEARD_WITHIN or not n.get("usefulness_score"):
            continue
        picked.append({
            "name": short_name(n.get("name") or n["public_key"][:8]),
            "score": n["usefulness_score"],
            "relays": n.get("relay_count_24h") or 0,
            "neighbours": neighbours.get(n["public_key"].lower(), 0),
        })
    picked.sort(key=lambda r: (r["score"], r["relays"]), reverse=True)
    return picked[:COUNT]


def plural(n, word):
    return f"{n:,} {word}" if n == 1 else f"{n:,} {word}s"


def render(top):
    cards = "\n".join(
        f'      <li class="card node"><h3>{html.escape(r["name"])}</h3>'
        f'<span class="mono">{plural(r["neighbours"], "neighbour")}<br>{r["relays"]:,} relayed in 24 h</span></li>'
        for r in top
    )
    return f'<ul class="g4" style="list-style: none; margin: 0; padding: 0;">\n{cards}\n    </ul>\n'


def write(text):
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, OUT)  # nginx never reads half a file


def once():
    nodes = get("/api/nodes?role=repeater&limit=5000")["nodes"]
    graph = get("/api/analytics/neighbor-graph")["nodes"]
    neighbours = {g["pubkey"].lower(): g.get("neighbor_count", 0) for g in graph}
    top = rank(nodes, neighbours, datetime.now(timezone.utc))
    if len(top) < COUNT // 2:  # CoreScope just restarted, or something's wrong: keep the last list
        raise RuntimeError(f"only {len(top)} repeaters ranked")
    write(render(top))
    return top


def main():
    while True:
        try:
            top = once()
            print("backbone:", ", ".join(r["name"] for r in top), flush=True)
        except Exception as e:  # noqa: BLE001 - any failure keeps the last fragment
            print(f"backbone: fetch failed, keeping the last list: {e}", file=sys.stderr, flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()

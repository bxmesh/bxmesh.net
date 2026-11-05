"""BxMesh's backbone: the eight repeaters the network uses the most, for /repeaters/.

Runs beside nginx in each site pod. Every INTERVAL seconds it reads CoreScope's public API,
ranks the region's repeaters and writes the cards as an HTML fragment to OUT, which nginx
includes into the page as it serves it (site/nginx.conf, server-side includes). So a visitor
never waits on CoreScope, and the page needs no JavaScript. If a fetch fails the last fragment
stays; until the first one, the page shows its own fallback list.

The ranking is traffic alone: how often each repeater appeared as a relay hop in the last 24
hours (CoreScope's relay_count_24h), shown as an hourly average. Not CoreScope's neighbour counts
or its usefulness score, which leans on them: they over-count (53 neighbours for Mt Bindo; the
owner, 5 November). Only repeaters placed in the region, and heard in the last day, count.
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


def rank(nodes, now):
    """The top COUNT repeaters in REGION, heard within HEARD_WITHIN, by packets relayed."""
    picked = []
    for n in nodes:
        regions = (n.get("region_placement") or {}).get("regions") or []
        if n.get("role") != "repeater" or n.get("foreign") or REGION not in regions:
            continue
        try:
            heard = datetime.fromisoformat(n["last_seen"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError):
            continue
        relays = n.get("relay_count_24h") or 0
        if now - heard > HEARD_WITHIN or relays <= 0:
            continue
        picked.append({"name": short_name(n.get("name") or n["public_key"][:8]), "relays": relays})
    picked.sort(key=lambda r: r["relays"], reverse=True)
    return picked[:COUNT]


def render(top):
    cards = "\n".join(
        f'      <li class="card node"><h3>{html.escape(r["name"])}</h3>'
        f'<span class="mono">{max(1, round(r["relays"] / 24)):,} relayed an hour</span></li>'
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
    top = rank(nodes, datetime.now(timezone.utc))
    # CoreScope reports no relays for a few minutes after it starts, or something's wrong: keep
    # the last list.
    if len(top) < COUNT // 2:
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

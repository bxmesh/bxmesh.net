"""backbone.py's ranking, its HTML and its heartbeat, without CoreScope."""

import os
import tempfile
import time
import unittest
from datetime import datetime, timezone
from unittest import mock

import backbone

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)


def node(name, relays, region="BHS", seen="2026-11-05T11:00:00Z", **kw):
    n = {"public_key": name.encode().hex().ljust(64, "0"), "name": name, "role": "repeater",
         "relay_count_24h": relays, "last_seen": seen,
         "region_placement": {"regions": [region] if region else []}}
    n.update(kw)
    return n


class Rank(unittest.TestCase):
    def test_order_and_filters(self):
        nodes = [
            node("Low", 100), node("High Rptr", 4800, usefulness_score=0.1), node("Mid", 2000),
            node("Elsewhere", 9999, region="SYD"), node("Unplaced", 9998, region=None),
            node("Foreign", 9997, foreign=True), node("Stale", 9996, seen="2026-11-03T00:00:00Z"),
            node("Silent", 0), node("Companion", 9995, role="companion"),
        ]
        top = backbone.rank(nodes, NOW)
        self.assertEqual([r["name"] for r in top], ["High", "Mid", "Low"])
        self.assertEqual(top[0]["relays"], 4800)

    def test_count(self):
        top = backbone.rank([node(f"R{i}", i) for i in range(1, 20)], NOW)
        self.assertEqual(len(top), backbone.COUNT)
        self.assertEqual(top[0]["name"], "R19")

    def test_short_name(self):
        self.assertEqual(backbone.short_name("🐝 Mt Bindo Rptr"), "🐝 Mt Bindo")
        self.assertEqual(backbone.short_name("🐝 Kelso Repeater"), "🐝 Kelso")
        self.assertEqual(backbone.short_name("Repeater"), "Repeater")
        self.assertEqual(backbone.short_name("Blackheath  RT"), "Blackheath RT")


class Render(unittest.TestCase):
    def test_escapes_and_counts(self):
        out = backbone.render([{"name": "<b>&Co", "relays": 4773}, {"name": "Quiet", "relays": 5}])
        self.assertIn("&lt;b&gt;&amp;Co", out)
        self.assertIn("199 relayed an hour", out)
        self.assertIn("1 relayed an hour", out)
        self.assertNotIn("<b>", out)


class Turn(unittest.TestCase):
    """Each turn rewrites the heartbeat, whether CoreScope answers or not."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = os.path.join(tmp.name, "backbone.html")
        self.heartbeat = os.path.join(tmp.name, "heartbeat")
        for name, value in (("OUT", self.out), ("HEARTBEAT", self.heartbeat)):
            patcher = mock.patch.object(backbone, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def beat_age(self):
        return time.time() - os.stat(self.heartbeat).st_mtime

    def test_fetch_works(self):
        seen = datetime.now(timezone.utc).isoformat()
        nodes = {"nodes": [node(f"R{i}", i, seen=seen) for i in range(1, 9)]}
        with mock.patch.object(backbone, "get", return_value=nodes), mock.patch("sys.stdout"):
            backbone.turn()
        self.assertLess(self.beat_age(), 5)
        self.assertTrue(os.path.exists(self.out))

    def test_fetch_fails(self):
        with mock.patch.object(backbone, "get", side_effect=OSError("CoreScope down")), \
                mock.patch("sys.stderr"):
            backbone.turn()
        self.assertLess(self.beat_age(), 5)
        self.assertFalse(os.path.exists(self.out))


if __name__ == "__main__":
    unittest.main()

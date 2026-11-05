"""backbone.py's ranking and its HTML, without CoreScope."""

import unittest
from datetime import datetime, timezone

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


if __name__ == "__main__":
    unittest.main()

"""backbone.py's ranking and its HTML, without CoreScope."""

import unittest
from datetime import datetime, timezone

import backbone

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)


def node(name, score, relays=0, region="BHS", seen="2026-11-05T11:00:00Z", **kw):
    n = {"public_key": name.encode().hex().ljust(64, "0"), "name": name, "role": "repeater",
         "usefulness_score": score, "relay_count_24h": relays, "last_seen": seen,
         "region_placement": {"regions": [region] if region else []}}
    n.update(kw)
    return n


class Rank(unittest.TestCase):
    def test_order_and_filters(self):
        nodes = [
            node("Low", 0.1), node("High Rptr", 0.9, relays=5), node("Mid", 0.5),
            node("Elsewhere", 0.99, region="SYD"), node("Unplaced", 0.98, region=None),
            node("Foreign", 0.97, foreign=True), node("Stale", 0.96, seen="2026-11-03T00:00:00Z"),
            node("Unscored", 0), node("Companion", 0.95, role="companion"),
        ]
        top = backbone.rank(nodes, {nodes[1]["public_key"]: 12}, NOW)
        self.assertEqual([r["name"] for r in top], ["High", "Mid", "Low"])
        self.assertEqual(top[0]["neighbours"], 12)
        self.assertEqual(top[1]["neighbours"], 0)

    def test_count(self):
        top = backbone.rank([node(f"R{i}", i / 100) for i in range(1, 20)], {}, NOW)
        self.assertEqual(len(top), backbone.COUNT)
        self.assertEqual(top[0]["name"], "R19")

    def test_short_name(self):
        self.assertEqual(backbone.short_name("🐝 Mt Bindo Rptr"), "🐝 Mt Bindo")
        self.assertEqual(backbone.short_name("🐝 Kelso Repeater"), "🐝 Kelso")
        self.assertEqual(backbone.short_name("Repeater"), "Repeater")
        self.assertEqual(backbone.short_name("Blackheath  RT"), "Blackheath RT")


class Render(unittest.TestCase):
    def test_escapes_and_counts(self):
        out = backbone.render([{"name": "<b>&Co", "neighbours": 1, "relays": 4773}])
        self.assertIn("&lt;b&gt;&amp;Co", out)
        self.assertIn("1 neighbour<br>4,773 relayed in 24 h", out)
        self.assertNotIn("<b>", out)


if __name__ == "__main__":
    unittest.main()

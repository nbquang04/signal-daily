import unittest
from datetime import datetime, timezone

from daily_news.collectors import clean_html, rank_and_dedupe
from daily_news.models import Item
from daily_news.pipeline import local_today


class CoreTests(unittest.TestCase):
    def test_clean_html(self):
        self.assertEqual(clean_html("<p>Hello&nbsp; world</p>"), "Hello world")

    def test_dedupe_and_limits(self):
        items = [
            Item("Same title", "https://a.test/1", "A", "technology", score=2),
            Item("Same title", "https://b.test/2", "B", "technology", score=1),
            Item("Other", "https://a.test/3?utm=x", "A", "technology", score=3),
        ]
        result = rank_and_dedupe(items, {"technology": 2})
        self.assertEqual([x.title for x in result], ["Other", "Same title"])

    def test_report_date_uses_vietnam_timezone_not_runner_utc(self):
        runner_time = datetime(2026, 8, 4, 21, 34, tzinfo=timezone.utc)
        self.assertEqual(local_today("Asia/Ho_Chi_Minh", runner_time).isoformat(), "2026-08-05")


if __name__ == "__main__":
    unittest.main()

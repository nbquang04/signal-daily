import json
import unittest
import uuid
from datetime import date
from pathlib import Path

from daily_news.storage import archive_completed_months, database_dates, get_archived_report, save_report


class StorageTests(unittest.TestCase):
    def test_monthly_archive_removes_database_rows_but_remains_readable(self):
        token = uuid.uuid4().hex
        root = Path("data")
        root.mkdir(exist_ok=True)
        database, archives = root / f"test-{token}.db", root / f"test-archives-{token}"
        try:
            for day in ("2026-07-30", "2026-07-31", "2026-08-01"):
                save_report(database, {"date": day, "generated_at": day + "T00:00:00Z", "items": [{"title": day}], "markets": [], "warnings": []})
            result = archive_completed_months(database, archives, date(2026, 8, 4))
            self.assertEqual(result[0]["reports"], 2)
            self.assertEqual(database_dates(database), ["2026-08-01"])
            self.assertEqual(get_archived_report(archives, "2026-07-31")["items"][0]["title"], "2026-07-31")
            self.assertTrue((archives / "2026-07.json.gz").is_file())
        finally:
            for suffix in ("", "-wal", "-shm"):
                Path(str(database) + suffix).unlink(missing_ok=True)
            if archives.exists():
                for path in archives.iterdir():
                    path.unlink()
                archives.rmdir()


if __name__ == "__main__":
    unittest.main()

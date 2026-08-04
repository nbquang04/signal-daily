import argparse
import json
from datetime import date
from pathlib import Path

from .storage import archive_completed_months, archive_month


def main():
    parser = argparse.ArgumentParser(description="Archive completed monthly reports")
    parser.add_argument("--database", type=Path, default=Path("data/daily_news.db"))
    parser.add_argument("--archives", type=Path, default=Path("data/archives"))
    parser.add_argument("--month", help="Archive one explicit month as YYYY-MM")
    args = parser.parse_args()
    result = [archive_month(args.database, args.archives, args.month)] if args.month else archive_completed_months(args.database, args.archives, date.today())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

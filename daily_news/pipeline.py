import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .collectors import collect_feed, collect_finance, collect_github, rank_and_dedupe
from .enrich import enrich_bilingual
from .gemini import analyze_opportunities
from .render import render_all
from .storage import archive_completed_months, save_report


def local_today(timezone_name: str, now: datetime | None = None) -> date:
    """Return the calendar date in the configured market timezone."""
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(ZoneInfo(timezone_name)).date()


def run(config_path: Path, output_dir: Path, run_date: date) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    items, warnings = [], []
    for feed in config.get("feeds", []):
        try:
            items.extend(collect_feed(feed))
        except Exception as exc:
            warnings.append(f"Feed {feed.get('name', feed.get('url'))} failed: {type(exc).__name__}")
    try:
        items.extend(collect_github(config.get("github", {}), run_date))
    except Exception as exc:
        warnings.append(f"GitHub collection failed: {type(exc).__name__}")
    selected = rank_and_dedupe(items, {**config.get("limits", {}), "github": config.get("github", {}).get("limit", 10)})
    enrich_bilingual(selected, config.get("openai", {}), warnings)
    markets = collect_finance(config.get("finance", {}).get("symbols", {}))
    insights = analyze_opportunities(selected, markets, run_date, warnings)
    existing_json = output_dir / f"{run_date.isoformat()}.json"
    if insights.get("status") != "ready" and existing_json.exists():
        try:
            previous_insights = json.loads(existing_json.read_text(encoding="utf-8")).get("insights", {})
            if previous_insights.get("status") == "ready":
                insights = previous_insights
                warnings.append("Gemini quota unavailable; preserved the last successful opportunity analysis.")
        except (OSError, ValueError):
            pass
    paths = render_all(output_dir, run_date, selected, markets, warnings, Path(config.get("frontend_dir", "web")), insights)
    storage = config.get("storage", {})
    database = Path(storage.get("database", "data/daily_news.db"))
    archive_dir = Path(storage.get("archive_dir", "data/archives"))
    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    save_report(database, payload)
    archived = archive_completed_months(database, archive_dir, run_date)
    return {"items": len(selected), "markets": len(markets), "warnings": warnings, "database": str(database), "archived": archived, "paths": {k: str(v) for k, v in paths.items()}}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a bilingual daily technology and finance brief")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--date", type=date.fromisoformat, help="Override report date (YYYY-MM-DD)")
    args = parser.parse_args()
    if args.date is None:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        args.date = local_today(config.get("timezone", "Asia/Ho_Chi_Minh"))
    result = run(args.config, args.output, args.date)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

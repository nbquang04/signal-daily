import json
import math
import re
import time
import urllib.parse
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape

from .models import Item

USER_AGENT = "DailyNewsIntelligence/0.1 (+personal research tool)"


def fetch(url: str, timeout: int = 20) -> bytes:
    # Convert internationalized query text (for example Vietnamese keywords)
    # to an ASCII-safe URL while preserving URL delimiters.
    url = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def clean_html(value: str | None) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _child_text(node: ET.Element, names: tuple[str, ...]) -> str:
    for child in node.iter():
        tag = child.tag.rsplit("}", 1)[-1].lower()
        if tag in names and child.text:
            return child.text.strip()
    return ""


def collect_feed(feed: dict) -> list[Item]:
    root = ET.fromstring(fetch(feed["url"]))
    entries = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1].lower() in ("item", "entry")]
    result = []
    for entry in entries:
        title = clean_html(_child_text(entry, ("title",)))
        link = _child_text(entry, ("link",))
        if not link:
            link_node = next((n for n in entry.iter() if n.tag.rsplit("}", 1)[-1].lower() == "link"), None)
            link = link_node.attrib.get("href", "") if link_node is not None else ""
        description = clean_html(_child_text(entry, ("description", "summary", "content")))
        published = _child_text(entry, ("pubdate", "published", "updated", "date"))
        if title and link:
            result.append(Item(title, link, feed["name"], feed["category"], feed.get("market", "global"), published, description[:1000]))
    return result


def collect_github(config: dict, run_date: date) -> list[Item]:
    since = run_date - timedelta(days=int(config.get("lookback_days", 14)))
    languages = config.get("languages", [])
    queries = [f"created:>={since.isoformat()} stars:>={config.get('min_stars', 30)}" + (f" language:{language}" if language else "") for language in (languages or [""])]
    repositories = {}
    for query in queries:
        url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode({"q": query, "sort": "stars", "order": "desc", "per_page": config.get("limit", 10)})
        payload = json.loads(fetch(url).decode("utf-8"))
        for repo in payload.get("items", []):
            repositories[repo["full_name"]] = repo
    result = []
    for repo in repositories.values():
        stars = int(repo.get("stargazers_count", 0))
        age = max(1, (run_date - date.fromisoformat(repo["created_at"][:10])).days)
        velocity = stars / age
        result.append(Item(
            title=repo["full_name"], url=repo["html_url"], source="GitHub", category="github",
            published=repo["created_at"], description=repo.get("description") or "",
            score=round(math.log1p(stars) * 10 + velocity, 2),
            meta={"stars": stars, "forks": repo.get("forks_count", 0), "language": repo.get("language"), "stars_per_day": round(velocity, 1)}
        ))
    return sorted(result, key=lambda item: item.score, reverse=True)[:int(config.get("limit", 10))]


def collect_finance(symbols: dict[str, str]) -> list[dict]:
    result = []
    now = int(time.time())
    for name, symbol in symbols.items():
        encoded = urllib.parse.quote(symbol, safe="")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?period1={now-604800}&period2={now}&interval=1d"
        try:
            chart = json.loads(fetch(url).decode("utf-8"))["chart"]["result"][0]
            closes = [x for x in chart["indicators"]["quote"][0]["close"] if x is not None]
            if not closes:
                continue
            change = ((closes[-1] / closes[-2]) - 1) * 100 if len(closes) > 1 else 0
            result.append({"name": name, "symbol": symbol, "price": round(closes[-1], 4), "change_pct": round(change, 2), "currency": chart.get("meta", {}).get("currency", "")})
        except (KeyError, IndexError, TypeError, ValueError, urllib.error.URLError):
            continue
    return result


def parsed_timestamp(value: str) -> float:
    if not value:
        return 0
    try:
        return parsedate_to_datetime(value).timestamp()
    except (TypeError, ValueError, OverflowError):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0


def rank_and_dedupe(items: list[Item], limits: dict) -> list[Item]:
    seen_urls, seen_titles, unique = set(), set(), []
    for item in sorted(items, key=lambda x: (x.score, parsed_timestamp(x.published)), reverse=True):
        url_key = item.url.split("?", 1)[0].rstrip("/").lower()
        title_key = re.sub(r"\W+", " ", item.title.lower()).strip()
        if url_key in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(url_key)
        seen_titles.add(title_key)
        unique.append(item)
    output = []
    counts: dict[str, int] = {}
    for item in unique:
        limit = int(limits.get(item.category, 10))
        if counts.get(item.category, 0) < limit:
            output.append(item)
            counts[item.category] = counts.get(item.category, 0) + 1
    return output

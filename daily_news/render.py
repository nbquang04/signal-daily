import json
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

from .models import Item

CATEGORY_NAMES = {
    "technology": ("Công nghệ", "Technology"),
    "github": ("GitHub mới nổi", "Emerging GitHub repositories"),
    "finance": ("Tin tài chính", "Financial news"),
    "society": ("Nhu cầu xã hội", "Societal needs"),
}


def _markdown_section(items: list[Item], language: str) -> str:
    chunks = []
    for category, names in CATEGORY_NAMES.items():
        rows = [x for x in items if x.category == category]
        if not rows:
            continue
        chunks.append(f"## {names[0 if language == 'vi' else 1]}")
        for item in rows:
            title = item.title_vi if language == "vi" else item.title_en
            summary = item.summary_vi if language == "vi" else item.summary_en
            meta = ""
            if item.category == "github":
                meta = f" — ⭐ {item.meta.get('stars', 0)} · {item.meta.get('language') or 'N/A'} · +{item.meta.get('stars_per_day', 0)}/day"
            chunks.append(f"### [{title}]({item.url}){meta}\n\n{summary}\n\n*{item.source}*\n")
    return "\n".join(chunks)


def render_all(output_dir: Path, run_date: date, items: list[Item], markets: list[dict], warnings: list[str], web_dir: Path | None = None, insights: dict | None = None) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = run_date.isoformat()
    disclaimer_vi = "> Dữ liệu tài chính chỉ mang tính tham khảo, không phải lời khuyên đầu tư."
    disclaimer_en = "> Financial data is informational only and is not investment advice."
    market_md = "\n".join(f"| {m['name']} | {m['price']:,.4f} {m['currency']} | {m['change_pct']:+.2f}% |" for m in markets)
    vi = f"# Bản tin hằng ngày — {stem}\n\n{disclaimer_vi}\n\n## Tổng quan thị trường\n\n| Tài sản | Giá gần nhất | Thay đổi ngày |\n|---|---:|---:|\n{market_md}\n\n{_markdown_section(items, 'vi')}"
    en = f"# Daily intelligence brief — {stem}\n\n{disclaimer_en}\n\n## Market snapshot\n\n| Asset | Latest | Daily change |\n|---|---:|---:|\n{market_md}\n\n{_markdown_section(items, 'en')}"
    vi_path, en_path, json_path, html_path = [output_dir / f"{stem}.{ext}" for ext in ("vi.md", "en.md", "json", "html")]
    vi_path.write_text(vi, encoding="utf-8")
    en_path.write_text(en, encoding="utf-8")
    payload = {"date": stem, "generated_at": datetime.now(timezone.utc).isoformat(), "markets": markets, "items": [x.to_dict() for x in items], "insights": insights or {"status": "unavailable", "opportunities": []}, "warnings": warnings}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if web_dir is not None:
        data_dir = web_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / f"{stem}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        dates = sorted((path.stem for path in data_dir.glob("????-??-??.json")), reverse=True)
        (data_dir / "index.json").write_text(json.dumps({"dates": dates, "latest": dates[0] if dates else None}, indent=2), encoding="utf-8")
    cards = "".join(
        f'<article><span>{escape(CATEGORY_NAMES[x.category][0])} · {escape(x.source)}</span><h3><a href="{escape(x.url)}">{escape(x.title_vi)}</a></h3><p>{escape(x.summary_vi)}</p><hr><h3>{escape(x.title_en)}</h3><p>{escape(x.summary_en)}</p></article>'
        for x in items
    )
    ticker = "".join(f'<div><b>{escape(m["name"])}</b><strong>{m["price"]:,.4f}</strong><em class="{"up" if m["change_pct"] >= 0 else "down"}">{m["change_pct"]:+.2f}%</em></div>' for m in markets)
    html = f'''<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Daily Brief {stem}</title><style>
    :root{{--ink:#17211b;--paper:#f3f0e7;--accent:#d55b35;--muted:#6c746e}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 system-ui,sans-serif}}header,main{{max-width:1120px;margin:auto;padding:40px 24px}}header{{border-bottom:1px solid #b9b9ad}}h1{{font:700 clamp(2.6rem,7vw,6rem)/.92 Georgia,serif;max-width:900px;margin:.2em 0}}header p,span{{color:var(--muted)}}.ticker{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1px;background:#bbb;margin:30px 0}}.ticker div{{background:var(--paper);padding:15px;display:grid}}strong{{font-size:1.2rem}}em{{font-style:normal}}.up{{color:#167348}}.down{{color:#b33d2e}}section{{columns:2 340px;column-gap:24px}}article{{break-inside:avoid;border-top:4px solid var(--ink);padding:18px 0 28px;margin-bottom:24px}}article h3{{font:700 1.35rem/1.25 Georgia,serif}}a{{color:inherit;text-decoration-thickness:1px;text-underline-offset:3px}}hr{{border:0;border-top:1px solid #ccc;margin:18px 0}}footer{{padding:30px 24px;text-align:center;color:var(--muted)}}
    </style></head><body><header><p>DAILY NEWS INTELLIGENCE · {stem}</p><h1>Thế giới hôm nay.<br>Today’s signals.</h1><div class="ticker">{ticker}</div></header><main><section>{cards}</section></main><footer>Informational only · Chỉ mang tính tham khảo</footer></body></html>'''
    html_path.write_text(html, encoding="utf-8")
    return {"vi": vi_path, "en": en_path, "json": json_path, "html": html_path, **({"frontend": web_dir / "index.html"} if web_dir else {})}

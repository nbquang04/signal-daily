import json
import os
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import Item


def _fallback(item: Item) -> None:
    text = item.description or item.title
    item.title_en = item.title
    item.title_vi = item.title
    item.summary_en = text[:320]
    item.summary_vi = text[:320]


def _google_translate(text: str, target: str) -> str:
    if not text.strip():
        return ""
    query = urllib.parse.urlencode({"client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": text[:1200]})
    request = urllib.request.Request(
        f"https://translate.googleapis.com/translate_a/single?{query}",
        headers={"User-Agent": "Mozilla/5.0 DailyNewsIntelligence/0.1"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return "".join(part[0] for part in payload[0] if part and part[0]).strip()


def _free_translation(items: list[Item], warnings: list[str]) -> None:
    jobs = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for index, item in enumerate(items):
            source_summary = (item.description or item.title)[:700]
            for language in ("vi", "en"):
                jobs[pool.submit(_google_translate, item.title, language)] = (index, f"title_{language}")
                jobs[pool.submit(_google_translate, source_summary, language)] = (index, f"summary_{language}")
        failures = 0
        for future in as_completed(jobs):
            index, field = jobs[future]
            try:
                setattr(items[index], field, future.result())
            except Exception:
                failures += 1
    for item in items:
        original = item.description or item.title
        item.title_vi = item.title_vi or item.title
        item.title_en = item.title_en or item.title
        item.summary_vi = item.summary_vi or original[:320]
        item.summary_en = item.summary_en or original[:320]
    if failures:
        warnings.append(f"Free translation fallback could not translate {failures} fields; original text was retained for those fields.")


def enrich_bilingual(items: list[Item], config: dict, warnings: list[str]) -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        _free_translation(items, warnings)
        return

    model = os.getenv("OPENAI_MODEL", config.get("model", "gpt-4.1-mini"))
    batch_size = int(config.get("batch_size", 12))
    for start in range(0, len(items), batch_size):
        batch = items[start:start + batch_size]
        compact = [{"id": i, "title": x.title, "description": x.description[:800], "category": x.category} for i, x in enumerate(batch)]
        prompt = (
            "You edit a factual daily intelligence brief. For every input item return concise Vietnamese and English. "
            "Do not invent facts; preserve names and numbers. Each summary must be 1-2 sentences and explain why it matters. "
            "Return only JSON with key 'items', an array containing id, title_vi, title_en, summary_vi, summary_en.\nINPUT:\n"
            + json.dumps(compact, ensure_ascii=False)
        )
        body = json.dumps({
            "model": model,
            "input": prompt,
            "text": {"format": {"type": "json_schema", "name": "bilingual_news", "strict": True, "schema": {
                "type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
                    "id": {"type": "integer"}, "title_vi": {"type": "string"}, "title_en": {"type": "string"},
                    "summary_vi": {"type": "string"}, "summary_en": {"type": "string"}},
                    "required": ["id", "title_vi", "title_en", "summary_vi", "summary_en"], "additionalProperties": False}}},
                "required": ["items"], "additionalProperties": False
            }}}
        }).encode("utf-8")
        request = urllib.request.Request("https://api.openai.com/v1/responses", data=body, method="POST", headers={
            "Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "User-Agent": "DailyNewsIntelligence/0.1"
        })
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.loads(response.read().decode("utf-8"))
            text = next(part["text"] for output in payload["output"] for part in output.get("content", []) if part.get("type") == "output_text")
            translated = json.loads(text)["items"]
            for row in translated:
                target = batch[int(row["id"])]
                for field in ("title_vi", "title_en", "summary_vi", "summary_en"):
                    setattr(target, field, row[field])
        except Exception as exc:
            warnings.append(f"AI enrichment batch {start // batch_size + 1} failed: {type(exc).__name__}")
            for item in batch:
                _fallback(item)

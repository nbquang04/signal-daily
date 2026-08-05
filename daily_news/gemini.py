"""AI-backed opportunity analysis and grounded chat.

NVIDIA's OpenAI-compatible endpoint is preferred; Gemini remains a fallback.
"""

import json
import os
import re
import urllib.error
import urllib.request
from datetime import date
from typing import Any

from .models import Item


def _generate_nvidia(prompt: str, *, json_mode: bool = False) -> str:
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY is not configured")
    base_url = os.getenv("AI_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
    model = os.getenv("AI_MODEL", "z-ai/glm-5.2")
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "top_p": 0.9,
        "max_tokens": 6000,
        "stream": False,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}", "User-Agent": "SignalDaily/0.3"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("NVIDIA returned no response")
    return str(choices[0].get("message", {}).get("content") or "").strip()


def _generate_gemini(prompt: str, *, json_mode: bool = False) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 6000},
    }
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key, "User-Agent": "SignalDaily/0.2"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = json.loads(response.read().decode("utf-8"))
    candidates = payload.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no response")
    return "".join(part.get("text", "") for part in candidates[0]["content"].get("parts", [])).strip()


def _generate(prompt: str, *, json_mode: bool = False) -> str:
    provider = os.getenv("AI_PROVIDER", "nvidia" if os.getenv("NVIDIA_API_KEY") else "gemini").lower()
    if provider == "nvidia":
        return _generate_nvidia(prompt, json_mode=json_mode)
    if provider == "gemini":
        return _generate_gemini(prompt, json_mode=json_mode)
    raise RuntimeError(f"Unsupported AI_PROVIDER: {provider}")


def _model_name() -> str:
    provider = os.getenv("AI_PROVIDER", "nvidia" if os.getenv("NVIDIA_API_KEY") else "gemini").lower()
    return os.getenv("AI_MODEL", "z-ai/glm-5.2") if provider == "nvidia" else os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


def analyze_opportunities(items: list[Item], markets: list[dict], run_date: date, warnings: list[str]) -> dict[str, Any]:
    if not (os.getenv("NVIDIA_API_KEY") or os.getenv("GEMINI_API_KEY")):
        return {"status": "unavailable", "opportunities": []}
    evidence = [{"id": i + 1, "title": item.title_en or item.title, "summary": item.summary_en or item.description,
                 "category": item.category, "market": item.market, "source": item.source, "url": item.url}
                for i, item in enumerate(items)]
    prompt = f"""You are a bilingual SaaS opportunity analyst. Analyze only the supplied public-news evidence for {run_date.isoformat()}.
Find up to 5 recurring, monetizable pain points affecting people or businesses globally and/or in Vietnam. Do not invent market sizes.
Score each opportunity 0-100 using urgency, frequency, willingness to pay, solution gap, and MVP feasibility.
Keep every text field concise (maximum 35 words) so the JSON is complete.
Return ONLY valid JSON: {{"daily_thesis_vi":string,"daily_thesis_en":string,"opportunities":[{{"name_vi":string,"name_en":string,"pain_vi":string,"pain_en":string,"audience_vi":string,"audience_en":string,"mvp_vi":string,"mvp_en":string,"scope":"vietnam"|"global"|"both","score":integer,"evidence_ids":[integer],"risks_vi":string,"risks_en":string}}]}}.
Every evidence id must exist in INPUT. This is research, not financial advice.
INPUT: {json.dumps({'news': evidence, 'markets': markets}, ensure_ascii=False)}"""
    try:
        raw = _generate(prompt, json_mode=True).strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
        result = json.loads(raw)
        valid_ids = set(range(1, len(items) + 1))
        opportunities = []
        for opportunity in result.get("opportunities", [])[:5]:
            ids = [int(value) for value in opportunity.get("evidence_ids", []) if int(value) in valid_ids][:5]
            opportunity["evidence_ids"] = ids
            opportunity["score"] = max(0, min(100, int(opportunity.get("score", 0))))
            opportunity["sources"] = [{"title": evidence[i - 1]["title"], "url": evidence[i - 1]["url"], "source": evidence[i - 1]["source"]} for i in ids]
            opportunities.append(opportunity)
        return {"status": "ready", "model": _model_name(),
                "daily_thesis_vi": result.get("daily_thesis_vi", ""), "daily_thesis_en": result.get("daily_thesis_en", ""),
                "opportunities": opportunities}
    except urllib.error.HTTPError as exc:
        warnings.append(f"Gemini opportunity analysis failed: HTTP {exc.code}")
        return {"status": "error", "opportunities": []}
    except Exception as exc:
        warnings.append(f"Gemini opportunity analysis failed: {type(exc).__name__}")
        return {"status": "error", "opportunities": []}


def _relevant_items(report: dict[str, Any], question: str, limit: int = 12) -> list[dict[str, Any]]:
    words = set(re.findall(r"[\wÀ-ỹ]{3,}", question.lower()))
    scored = []
    for item in report.get("items", []):
        haystack = " ".join(str(item.get(key, "")) for key in ("title_vi", "title_en", "summary_vi", "summary_en", "category", "source")).lower()
        score = sum(1 for word in words if word in haystack)
        scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for score, item in scored[:limit] if score > 0] or [item for _, item in scored[:8]]


def answer_question(report: dict[str, Any], question: str, language: str = "vi") -> dict[str, Any]:
    relevant = _relevant_items(report, question)
    context = [{"id": i + 1, "title": item.get("title_en") or item.get("title"),
                "summary": item.get("summary_en") or item.get("description"), "source": item.get("source"), "url": item.get("url"),
                "market": item.get("market"), "category": item.get("category")} for i, item in enumerate(relevant)]
    prompt = f"""You are Signal Daily's SaaS Opportunity Analyst. Answer in {'Vietnamese' if language == 'vi' else 'English'}.
Use ONLY the supplied daily report and opportunity analysis. Separate facts from inference. Cite evidence inline as [1], [2].
Focus on pain points, target users, willingness to pay, solution gaps, MVP validation, technology and finance implications.
Never give personalized investment instructions; state uncertainty and challenge weak assumptions. Keep the answer under 700 words.
QUESTION: {question}
REPORT DATE: {report.get('date')}
OPPORTUNITY ANALYSIS: {json.dumps(report.get('insights', {}), ensure_ascii=False)}
EVIDENCE: {json.dumps(context, ensure_ascii=False)}"""
    answer = _generate(prompt)
    sources = [{"id": i + 1, "title": row["title"], "url": row["url"], "source": row["source"]} for i, row in enumerate(context)]
    return {"answer": answer, "sources": sources, "date": report.get("date")}

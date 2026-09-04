import json
import re
from dataclasses import dataclass
from typing import Optional

import httpx

from .config import settings


@dataclass
class AnalysisResult:
    category: str
    priority: str
    assigned_team: str
    summary: str
    status: str
    provider: str = "simulated"


TEAM_MAPPING = {
    "account_access": "identity-operations",
    "incident": "platform-operations",
    "billing": "finance-operations",
    "how_to": "customer-success",
    "general": "first-level-support",
}

CATEGORY_KEYWORDS = {
    "account_access": {
        "keywords": ["gesperrt", "anmelden", "login", "konto", "passwort", "zugriff", "locked", "account", "login"],
        "weight": 3,
    },
    "incident": {
        "keywords": [
            "nicht erreichbar", "ausgefallen", "down", "störung", "fehler",
            "produktionssystem", "produktivsystem", "seit heute", "nicht verfügbar",
        ],
        "weight": 4,
    },
    "billing": {
        "keywords": ["rechnung", "rechnungsadresse", "zahlung", "faktura", "invoice", "billing"],
        "weight": 3,
    },
    "how_to": {
        "keywords": ["wie kann ich", "wie ändere", "anleitung", "how to", "tutorial", "erklären"],
        "weight": 2,
    },
}

PRIORITY_SCORING = {
    "critical": {
        "keywords": [
            "produktionssystem", "produktionsumgebung", "production system",
            "produktivsystem", "produktions",
            "alle nutzer", "all users", "aller nutzer",
            "komplett ausgefallen", "totalausfall", "komplett down",
            "nicht erreichbar", "not reachable", "katastrophe",
        ],
        "weight": 5,
    },
    "high": {
        "keywords": [
            "dringend", "blockiert", "urgent", "blocked", "sofort",
            "nicht möglich", "gesperrt", "kein zugriff", "outage",
        ],
        "weight": 4,
    },
    "medium": {
        "keywords": ["störung", "fehler", "problem", "issues", "nicht laden"],
        "weight": 3,
    },
    "low": {
        "keywords": ["frage", "wie kann", "anleitung", "ändern", "änderung"],
        "weight": 2,
    },
}


def _score_category(text: str) -> tuple[str, int]:
    low = text.lower()
    best_category = "general"
    best_score = 0
    for cat, cfg in CATEGORY_KEYWORDS.items():
        score = 0
        for kw in cfg["keywords"]:
            if kw.lower() in low:
                score += cfg["weight"]
        if score > best_score:
            best_score = score
            best_category = cat
    return best_category, best_score


def _score_priority(text: str) -> str:
    low = text.lower()
    best_priority = "low"
    best_score = 0
    for prio, cfg in PRIORITY_SCORING.items():
        score = 0
        for kw in cfg["keywords"]:
            if kw.lower() in low:
                score += cfg["weight"]
        if score > best_score:
            best_score = score
            best_priority = prio
    return best_priority


def _summarize(text: str, category: str) -> str:
    summary = re.sub(r"\s+", " ", text).strip()
    if len(summary) > 100:
        summary = summary[:100].rsplit(" ", 1)[0] + "..."
    return summary


def simulate_ai(text: str) -> AnalysisResult:
    """Rule-based, explainable AI fallback with weighted keyword scoring."""
    category, _ = _score_category(text)
    priority = _score_priority(text)
    summary = _summarize(text, category)
    assigned_team = TEAM_MAPPING.get(category, TEAM_MAPPING["general"])

    status = "manual_review_required" if (category == "incident" and priority == "critical") else "open"

    return AnalysisResult(
        category=category,
        priority=priority,
        assigned_team=assigned_team,
        summary=summary,
        status=status,
        provider="simulated",
    )


def _http_llm_analyze(url: str, model: str, text: str, api_key: Optional[str] = None, provider: str = "llm") -> Optional[AnalysisResult]:
    """Analyze via an OpenAI-compatible HTTP endpoint (OpenAI or Ollama)."""
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You classify support tickets. Respond ONLY with a JSON object and no other text, "
                    "with exactly these keys: category (one of account_access, incident, billing, how_to, general), "
                    "priority (one of low, medium, high, critical), "
                    "assignedTeam (one of identity-operations, platform-operations, finance-operations, customer-success, first-level-support), "
                    "summary (a short English summary, max 30 words)."
                ),
            },
            {"role": "user", "content": text},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"} if api_key else None,
    }
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(f"{url}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
    except Exception:
        return None

    category = data.get("category", "general")
    priority = data.get("priority", "low")
    summary = data.get("summary", _summarize(text, category))
    if category not in TEAM_MAPPING:
        category = "general"
    if priority not in PRIORITY_SCORING:
        priority = "low"

    valid_teams = set(TEAM_MAPPING.values())
    llm_team = data.get("assignedTeam")
    team = llm_team if llm_team in valid_teams else TEAM_MAPPING.get(category, TEAM_MAPPING["general"])
    status = "manual_review_required" if (category == "incident" and priority == "critical") else "open"

    return AnalysisResult(
        category=category,
        priority=priority,
        assigned_team=team,
        summary=summary,
        status=status,
        provider=provider,
    )


def _analyze_openai(text: str) -> Optional[AnalysisResult]:
    url = "https://api.openai.com/v1"
    return _http_llm_analyze(url, "gpt-3.5-turbo", text, api_key=settings.openai_api_key, provider="openai")


def _analyze_ollama(text: str) -> Optional[AnalysisResult]:
    try:
        return _http_llm_analyze(settings.ollama_url, settings.ollama_model, text, provider="ollama")
    except Exception:
        return None


def analyze_request(text: str) -> AnalysisResult:
    """Provider cascade: openai -> ollama -> simulated rules."""
    provider = settings.ai_provider.lower()

    if provider in ("auto", "openai") and settings.openai_api_key:
        result = _analyze_openai(text)
        if result:
            return result

    if provider in ("auto", "ollama", "openai"):
        result = _analyze_ollama(text)
        if result:
            return result

    return simulate_ai(text)

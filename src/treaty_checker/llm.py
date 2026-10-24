"""Optional LLM step: choose which candidate clauses are relevant to a pasted clause.

The model only ever returns clause IDs, a short reasoning note and a confidence level.
Every ID is checked against the candidate list, and the quoted text always comes from
the database, never from the model. Works with any OpenAI-compatible endpoint
(Groq, OpenRouter, Ollama, ...), configured in .env.
"""
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path

import requests
from dotenv import load_dotenv

from treaty_checker.models import Clause

load_dotenv()

CONFIDENCE = {"high", "medium", "low"}

SYSTEM_PROMPT = """You help a human reviewer screen a pasted clause against provisions of international treaties.

You will receive a CLAUSE and a list of CANDIDATE treaty provisions, each with an ID in square brackets.
Choose the candidates that the clause may conflict with, restrict, or undermine.

Rules:
- Use only IDs that appear in the candidate list. Never invent an ID.
- A match means the clause would restrict, deny, undermine or conflict with the provision. A clause that merely repeats, implements or is consistent with a provision is NOT a match. A clause that only deals with unrelated administrative matters is NOT a match.
- Do not quote or reproduce treaty text. The reviewer will see the real text.
- Do not say whether the clause is lawful or whether a treaty has been violated. Only say which provisions it may conflict with and why.
- If none of the candidates is a match, return an empty list.
- Return at most 5 matches, most relevant first.

Answer with JSON only, in exactly this shape:
{"matches": [{"id": "<candidate id>", "reasoning": "<one or two sentences>", "confidence": "high|medium|low"}]}"""


class LLMError(Exception):
    """The LLM step failed (not configured, unreachable, or returned unusable output)."""


class DailyLimitError(LLMError):
    """The provider's per-day limit for this model is used up (waiting a few seconds won't help)."""


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    timeout: int = 120
    fallback_models: tuple[str, ...] = ()  # tried in order, same endpoint and key, if the daily limit is hit


@dataclass(frozen=True)
class Match:
    id: str
    reasoning: str
    confidence: str


@dataclass(frozen=True)
class LLMResult:
    matches: list[Match]
    rejected: list[str]  # IDs the model returned that were not in the candidate list
    model: str = ""            # which model produced this answer
    used_fallback: bool = False  # True if the primary model's daily limit was hit


def load_config() -> LLMConfig | None:
    base_url = os.getenv("LLM_BASE_URL")
    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL")
    if not (base_url and api_key and model):
        return None
    fallbacks = tuple(m.strip() for m in os.getenv("LLM_FALLBACK_MODELS", "").split(",") if m.strip())
    return LLMConfig(base_url.rstrip("/"), api_key, model, int(os.getenv("LLM_TIMEOUT", "120")), fallbacks)


def build_user_prompt(text: str, candidates: list[Clause]) -> str:
    lines = [f"[{c.id}] {c.citation}: {c.text}" for c in candidates]
    return f"CLAUSE:\n{text}\n\nCANDIDATES:\n" + "\n".join(lines)


def _wait_seconds(response: requests.Response, attempt: int) -> float:
    try:
        return min(float(response.headers.get("Retry-After", "")), 30.0)
    except ValueError:
        return float(2 ** (attempt + 1))


def _is_daily_limit(body: str) -> bool:
    body = (body or "").lower()
    return "per day" in body or "per-day" in body


def chat(config: LLMConfig, system: str, user: str) -> str:
    url = f"{config.base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}
    body = {
        "model": config.model,
        "temperature": 0,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
    }
    for attempt in range(4):
        try:
            r = requests.post(url, headers=headers, json=body, timeout=config.timeout)
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt < 3:  # dropped connection or timeout: wait and try again
                time.sleep(2 ** (attempt + 1))
                continue
            raise LLMError(f"could not reach the LLM endpoint: {e}") from e
        except requests.RequestException as e:
            raise LLMError(f"could not reach the LLM endpoint: {e}") from e
        if r.status_code == 400 and "response_format" in body:
            body.pop("response_format")  # some models/providers don't support JSON mode
            continue
        if r.status_code == 429 and _is_daily_limit(r.text):
            raise DailyLimitError(f"daily limit reached for {config.model}: {r.text[:200]}")
        if r.status_code in (429, 500, 502, 503) and attempt < 3:
            time.sleep(_wait_seconds(r, attempt))
            continue
        if r.status_code != 200:
            raise LLMError(f"LLM endpoint returned {r.status_code}: {r.text[:200]}")
        try:
            return r.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as e:
            raise LLMError("unexpected response format from the LLM endpoint") from e
    raise LLMError("the LLM endpoint kept failing")


def parse_and_validate(raw: str, allowed_ids: set[str], max_matches: int = 5) -> LLMResult:
    found = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not found:
        raise LLMError("the model's reply contained no JSON")
    try:
        data = json.loads(found.group(0))
    except json.JSONDecodeError as e:
        raise LLMError(f"the model's reply was not valid JSON: {e}") from e
    items = data.get("matches") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise LLMError("the model's reply had no 'matches' list")

    matches, rejected, seen = [], [], set()
    for item in items:
        if not isinstance(item, dict):
            continue
        clause_id = str(item.get("id", "")).strip()
        if clause_id not in allowed_ids:  # the model invented or mangled an ID
            rejected.append(clause_id)
            continue
        if clause_id in seen:
            continue
        seen.add(clause_id)
        confidence = str(item.get("confidence", "")).strip().lower()
        matches.append(Match(
            clause_id,
            str(item.get("reasoning", "")).strip()[:500],
            confidence if confidence in CONFIDENCE else "low",
        ))
        if len(matches) >= max_matches:
            break
    return LLMResult(matches, rejected)


def _cache_path() -> Path | None:
    value = os.getenv("LLM_CACHE", ".cache/llm_cache.json")
    return None if value.lower() in ("off", "none", "") else Path(value)


def _load_cache() -> dict[str, str]:
    path = _cache_path()
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_cache(cache: dict[str, str]) -> None:
    path = _cache_path()
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass  # the cache is only an optimisation


def _cache_key(model: str, system: str, user: str) -> str:
    return hashlib.sha256("\n".join((model, system, user)).encode("utf-8")).hexdigest()


def _ask(config: LLMConfig, prompt: str, allowed: set[str], cache: dict[str, str]) -> LLMResult:
    """One model: use a cached reply if there is one, otherwise ask (twice at most)."""
    key = _cache_key(config.model, SYSTEM_PROMPT, prompt)
    if key in cache:
        try:
            return parse_and_validate(cache[key], allowed)
        except LLMError:
            pass  # unusable cache entry: ask again
    for attempt in range(2):
        raw = chat(config, SYSTEM_PROMPT, prompt)  # network errors are retried inside chat()
        try:
            result = parse_and_validate(raw, allowed)
        except LLMError:
            if attempt == 1:  # the model sometimes returns an empty or non-JSON reply: ask once more
                raise
            continue
        cache[key] = raw  # only replies that parsed are cached
        _save_cache(cache)
        return result
    raise LLMError("the LLM endpoint kept failing")


def analyze(text: str, candidates: list[Clause], config: LLMConfig | None = None) -> LLMResult:
    config = config or load_config()
    if config is None:
        raise LLMError("the LLM is not configured (set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in .env)")
    prompt = build_user_prompt(text, candidates)
    allowed = {c.id for c in candidates}
    cache = _load_cache()
    last_limit: DailyLimitError | None = None
    for i, model in enumerate((config.model, *config.fallback_models)):
        try:
            result = _ask(replace(config, model=model), prompt, allowed, cache)
        except DailyLimitError as e:  # this model is used up for today: try the next one
            last_limit = e
            continue
        return replace(result, model=model, used_fallback=i > 0)
    raise last_limit or LLMError("no model available")
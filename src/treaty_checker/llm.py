"""Optional LLM step: choose which candidate clauses are relevant to a pasted clause.

The model only ever returns clause IDs, a short reasoning note and a confidence level.
Every ID is checked against the candidate list, and the quoted text always comes from
the database, never from the model. Works with any OpenAI-compatible endpoint
(Groq, OpenRouter, Ollama, ...), configured in .env.
"""
import json
import os
import re
import time
from dataclasses import dataclass

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


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    timeout: int = 120


@dataclass(frozen=True)
class Match:
    id: str
    reasoning: str
    confidence: str


@dataclass(frozen=True)
class LLMResult:
    matches: list[Match]
    rejected: list[str]  # IDs the model returned that were not in the candidate list


def load_config() -> LLMConfig | None:
    base_url = os.getenv("LLM_BASE_URL")
    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL")
    if not (base_url and api_key and model):
        return None
    return LLMConfig(base_url.rstrip("/"), api_key, model, int(os.getenv("LLM_TIMEOUT", "120")))


def build_user_prompt(text: str, candidates: list[Clause]) -> str:
    lines = [f"[{c.id}] {c.citation}: {c.text}" for c in candidates]
    return f"CLAUSE:\n{text}\n\nCANDIDATES:\n" + "\n".join(lines)


def _wait_seconds(response: requests.Response, attempt: int) -> float:
    try:
        return min(float(response.headers.get("Retry-After", "")), 30.0)
    except ValueError:
        return float(2 ** (attempt + 1))


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


def analyze(text: str, candidates: list[Clause], config: LLMConfig | None = None) -> LLMResult:
    config = config or load_config()
    if config is None:
        raise LLMError("the LLM is not configured (set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in .env)")
    raw = chat(config, SYSTEM_PROMPT, build_user_prompt(text, candidates))
    return parse_and_validate(raw, {c.id for c in candidates})
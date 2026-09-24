"""Minimal IEEE Xplore Metadata API client with response caching and a call budget.

Every successful response is cached under data/raw/api/, keyed by its query
parameters, so the same query never spends a second API call. Calls are
counted in data/api_calls.json over a rolling 24-hour window.

Usage as a probe:
    python scripts/xplore.py publication_title="Mixed and Augmented Reality" publication_year=2021
"""

import hashlib
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE_DIR = DATA / "raw" / "api"
CALL_LOG = DATA / "api_calls.json"

ENDPOINT = "https://ieeexploreapi.ieee.org/api/v1/search/articles"
DAILY_CAP = 200          # key allows 210/day; keep a margin
MIN_INTERVAL = 0.5       # seconds between calls; key allows 10/s
MAX_RECORDS = 25         # per-call maximum for this key


class BudgetExhausted(Exception):
    pass


def load_key():
    for line in (ROOT / ".env").read_text().splitlines():
        name, _, value = line.partition("=")
        if name.strip() == "IEEE_XPLORE_API_KEY":
            return value.strip().strip("'\"")
    raise RuntimeError("IEEE_XPLORE_API_KEY not found in .env")


def _load_calls():
    if CALL_LOG.exists():
        return json.loads(CALL_LOG.read_text())
    return []


def calls_last_24h():
    cutoff = time.time() - 24 * 3600
    return [t for t in _load_calls() if t > cutoff]


def remaining_budget():
    return DAILY_CAP - len(calls_last_24h())


def _record_call():
    calls = calls_last_24h()
    calls.append(time.time())
    CALL_LOG.parent.mkdir(parents=True, exist_ok=True)
    CALL_LOG.write_text(json.dumps(calls))


def _cache_path(params):
    canon = json.dumps(params, sort_keys=True)
    return CACHE_DIR / (hashlib.sha1(canon.encode()).hexdigest()[:16] + ".json")


_last_call = 0.0


def search(**params):
    """Run one search; return the parsed JSON response (from cache if possible)."""
    params = {k: str(v) for k, v in params.items()}
    params.setdefault("max_records", str(MAX_RECORDS))
    params.setdefault("format", "json")

    path = _cache_path(params)
    if path.exists():
        return json.loads(path.read_text())["response"]

    if remaining_budget() <= 0:
        raise BudgetExhausted("24-hour API call budget used up; rerun later")

    global _last_call
    wait = MIN_INTERVAL - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)

    resp = requests.get(ENDPOINT, params={**params, "apikey": load_key()}, timeout=60)
    _last_call = time.time()
    _record_call()  # count the call even if it failed; IEEE likely does too

    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
    data = resp.json()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"params": params, "response": data}, indent=1))
    return data


def summarize(data):
    print(f"total_records: {data.get('total_records')}")
    for a in data.get("articles", []):
        print(f"  {a.get('publication_year')} | {a.get('publication_number')} "
              f"| is={a.get('is_number')} | {a.get('content_type')} "
              f"| {a.get('publication_title')} | {a.get('title', '')[:60]}")


if __name__ == "__main__":
    kwargs = dict(arg.split("=", 1) for arg in sys.argv[1:])
    summarize(search(**kwargs))
    print(f"budget remaining (24h): {remaining_budget()}")

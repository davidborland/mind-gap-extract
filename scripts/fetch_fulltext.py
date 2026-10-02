"""Fetch paper full text as XML from the IEEE Xplore Full-Text API, resumably.

This uses the full-text access token (IEEE_XPLORE_FT_ACCESS_TOKEN in .env), so
it works from any network, for subscription and open-access papers alike:
  1. POST /auth/token with the API key and access token -> temporary cltoken,
     valid for 15 minutes; a new one is requested every TOKEN_LIFETIME seconds
  2. GET /search/document/<article>/fulltext with the cltoken -> XML <body>
     (sections, paragraphs, tables, captions; no abstract or references)

Files are saved as data/fulltext/<article_number>.xml only if the response has
a <body>. Every call (token or document) counts against the shared 24-hour
budget in xplore.py, so a run stops by itself when the budget is used up;
rerun the next day to resume. Existing files are skipped.

Stops on: budget exhausted, 5 consecutive failures, or repeated "Over Qps"
throttling. Every attempt is logged to data/logs/fulltext.csv, and console
output is copied to data/logs/fulltext_run.log.

Usage:
    python scripts/fetch_fulltext.py --limit 3     # small test
    python scripts/fetch_fulltext.py               # until the daily budget runs out
"""

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

import xplore

ROOT = xplore.ROOT
INDEX = ROOT / "data" / "index.csv"
XML_DIR = ROOT / "data" / "fulltext"
LOG = ROOT / "data" / "logs" / "fulltext.csv"
RUN_LOG = ROOT / "data" / "logs" / "fulltext_run.log"

API = "https://ieeexploreapi.ieee.org/api/v1"
TOKEN_LIFETIME = 12 * 60     # cltoken lasts 15 min; refresh early
QPS_WAIT = 60                # seconds to back off after "Over Qps"
QPS_RETRIES = 3
MAX_CONSECUTIVE_FAILURES = 5


class Stop(Exception):
    """A failure that means no further paper will succeed this run."""


class Client:
    def __init__(self, delay):
        self.key = xplore.load_key()
        self.access_token = xplore.load_env("IEEE_XPLORE_FT_ACCESS_TOKEN")
        self.delay = delay
        self.cltoken = None
        self.token_time = 0.0
        self.last_call = 0.0

    def _call(self, method, url, params):
        """One API call, paced, budgeted, retried on "Over Qps"."""
        for attempt in range(QPS_RETRIES + 1):
            if xplore.remaining_budget() <= 0:
                raise Stop("24-hour API call budget used up; rerun later")
            wait = self.delay - (time.time() - self.last_call)
            if wait > 0:
                time.sleep(wait)
            r = requests.request(method, url, params={**params, "apikey": self.key},
                                 timeout=(15, 120))
            self.last_call = time.time()
            xplore.record_call()
            if "Over Qps" not in r.text[:200]:
                return r
            if attempt < QPS_RETRIES:
                say(f"  throttled (Over Qps); waiting {QPS_WAIT} s")
                time.sleep(QPS_WAIT)
        raise Stop(f"still throttled after {QPS_RETRIES} retries (HTTP {r.status_code})")

    def token(self, force=False):
        if force or not self.cltoken or time.time() - self.token_time > TOKEN_LIFETIME:
            r = self._call("POST", f"{API}/auth/token", {"auth-token": self.access_token})
            try:
                self.cltoken = r.json()["token"]
            except (ValueError, KeyError):
                raise Stop(f"no cltoken: HTTP {r.status_code} {r.text[:200]!r}")
            self.token_time = time.time()
        return self.cltoken

    def fulltext(self, article):
        """Fetch one paper. Returns (status, http_code, bytes, note)."""
        url = f"{API}/search/document/{article}/fulltext"
        for retry in (False, True):
            params = {"format": "xml", "cltoken": self.token(force=retry)}
            r = self._call("GET", url, params)
            if r.status_code not in (401, 403):
                break  # a 401/403 may mean the cltoken expired early: refresh once
        if r.status_code != 200 or b"<body" not in r.content:
            return "failed", r.status_code, len(r.content), \
                " ".join(r.text[:150].split())
        XML_DIR.mkdir(parents=True, exist_ok=True)
        part = XML_DIR / f"{article}.xml.part"
        part.write_bytes(r.content)
        part.rename(XML_DIR / f"{article}.xml")
        return "ok", 200, len(r.content), ""


def has_body(path):
    try:
        return b"<body" in path.read_bytes()
    except OSError:
        return False


def log(article, status, code, size, note):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG.exists()
    with open(LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "article_number", "status", "http", "bytes", "note"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), article, status, code, size, note])


_run_log = None


def say(msg):
    print(msg)
    _run_log.write(msg + "\n")
    _run_log.flush()


def main():
    global _run_log
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--limit", type=int, default=None,
                    help="max papers to attempt this run (default: until budget runs out)")
    # At 2 s apart, IEEE answered "Over Qps" on 2 of 6 calls (2026-10-02).
    ap.add_argument("--delay", type=float, default=10.0,
                    help="minimum seconds between API calls (default 10)")
    args = ap.parse_args()

    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    _run_log = open(RUN_LOG, "a")
    say(f"=== {datetime.now().isoformat(timespec='seconds')} fetch_fulltext {' '.join(sys.argv[1:])}")

    papers = list(csv.DictReader(open(INDEX)))
    todo = [p for p in papers if not has_body(XML_DIR / f"{p['article_number']}.xml")]
    # Open-access papers first: whether the Full-Text API serves them (CC BY
    # records say "IEEE is not the copyright holder") is the untested part.
    todo.sort(key=lambda p: p["access_type"] == "LOCKED")
    remaining = len(todo)
    if args.limit is not None:
        todo = todo[:args.limit]
    say(f"{len(papers) - remaining} of {len(papers)} already fetched; attempting up to "
        f"{len(todo)} of {remaining} remaining; budget remaining (24h): {xplore.remaining_budget()}")

    ok = failed = consecutive = 0
    stopped = False
    try:
        client = Client(args.delay)
        for i, p in enumerate(todo):
            article = p["article_number"]
            try:
                status, code, size, note = client.fulltext(article)
            except Stop as e:
                log(article, "stopped", "", 0, str(e))
                say(f"STOPPED at {article}: {e}")
                stopped = True
                break
            except requests.RequestException as e:
                status, code, size, note = "failed", "", 0, type(e).__name__
            log(article, status, code, size, note)
            say(f"[{i + 1}] {article} {'locked' if p['access_type'] == 'LOCKED' else 'OA'} {status} {size // 1024} KB {note}")

            if status == "ok":
                ok, consecutive = ok + 1, 0
            else:
                failed, consecutive = failed + 1, consecutive + 1
                if consecutive >= MAX_CONSECUTIVE_FAILURES:
                    say(f"STOPPED: {consecutive} consecutive failures")
                    stopped = True
                    break
    except Exception as e:
        say(f"ERROR: {type(e).__name__}: {e}")
        raise
    finally:
        done = sum(has_body(XML_DIR / f"{p['article_number']}.xml") for p in papers)
        say(f"This run: {ok} fetched, {failed} failed. Total: {done} of {len(papers)} "
            f"in {XML_DIR.relative_to(ROOT)}. Budget remaining (24h): {xplore.remaining_budget()}")
    sys.exit(1 if stopped or failed else 0)


if __name__ == "__main__":
    main()

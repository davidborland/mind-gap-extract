"""Download paper PDFs from IEEE Xplore, slowly and resumably.

For each paper in data/index.csv this fetches the stamp.jsp page (which sets
session cookies and tells us whether this network is entitled to the PDF),
then the real PDF linked from its iframe. Files are saved as
data/pdfs/<article_number>.pdf only if they start with %PDF.

Safety rules, because bulk scraping can get the institution's IP range blocked:
  - one request at a time, with a random 5-10 s pause between papers
  - at most --limit papers per run (default 300)
  - stop immediately on a login redirect (network not entitled) or on
    HTTP 403/418/429 (blocked or throttled)
  - stop after 5 consecutive failures of any other kind

Existing valid PDFs are skipped, so rerunning resumes. Every attempt is logged
to data/logs/downloads.csv.

Usage:
    python scripts/download_pdfs.py --open-access-only --limit 5
    python scripts/download_pdfs.py            # needs an entitled network
"""

import argparse
import csv
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
import urllib3.util.connection

# IPv6 to Xplore's CDN hangs on some networks (seen 2026-09-24), and requests
# waits out the connect timeout on every IPv6 address before trying IPv4.
urllib3.util.connection.HAS_IPV6 = False

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data" / "index.csv"
PDF_DIR = ROOT / "data" / "pdfs"
LOG = ROOT / "data" / "logs" / "downloads.csv"

USER_AGENT = "Mozilla/5.0 (compatible; research-pdf-harvest)"
STAMP = "https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={}"
GET_PDF = "https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber={}&ref="
IFRAME = re.compile(r'<iframe[^>]+src="([^"]+)"', re.IGNORECASE)
MAX_CONSECUTIVE_FAILURES = 5


class Stop(Exception):
    """A failure that means no further paper will succeed on this network."""


def is_pdf(path):
    try:
        with open(path, "rb") as f:
            return f.read(5) == b"%PDF-"
    except OSError:
        return False


def download(session, article):
    """Fetch one paper's PDF. Returns (status, http_code, bytes, note)."""
    stamp_url = STAMP.format(article)
    r = session.get(stamp_url, allow_redirects=False, timeout=(15, 60))
    if r.status_code in (403, 418, 429):
        raise Stop(f"HTTP {r.status_code} on stamp page: blocked or throttled")
    if r.status_code in (301, 302) and "login" in r.headers.get("Location", ""):
        raise Stop("redirected to login: this network isn't entitled to the PDF")
    if r.status_code != 200:
        return "failed", r.status_code, 0, "stamp page error"

    m = IFRAME.search(r.text)
    pdf_url = m.group(1) if m else GET_PDF.format(article)
    time.sleep(random.uniform(1, 2))

    r = session.get(pdf_url, headers={"Referer": stamp_url}, timeout=(15, 120))
    if r.status_code in (403, 418, 429):
        raise Stop(f"HTTP {r.status_code} on PDF: blocked or throttled")
    if r.status_code != 200 or not r.content.startswith(b"%PDF-"):
        return "failed", r.status_code, len(r.content), \
            f"not a PDF ({r.headers.get('Content-Type', '?')})"

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    part = PDF_DIR / f"{article}.pdf.part"
    part.write_bytes(r.content)
    part.rename(PDF_DIR / f"{article}.pdf")
    return "ok", 200, len(r.content), "iframe" if m else "getPDF"


def log(article, status, code, size, note):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG.exists()
    with open(LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "article_number", "status", "http", "bytes", "note"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), article, status, code, size, note])


def main():
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--limit", type=int, default=300, help="max papers to attempt this run")
    ap.add_argument("--open-access-only", action="store_true",
                    help="only papers that don't need a subscription")
    ap.add_argument("--delay", type=float, nargs=2, default=(5, 10), metavar=("MIN", "MAX"),
                    help="seconds to pause between papers (default 5 10)")
    args = ap.parse_args()

    papers = list(csv.DictReader(open(INDEX)))
    if args.open_access_only:
        papers = [p for p in papers if p["access_type"] != "LOCKED"]
    todo = [p for p in papers if not is_pdf(PDF_DIR / f"{p['article_number']}.pdf")]
    print(f"{len(papers) - len(todo)} of {len(papers)} already downloaded; "
          f"attempting up to {min(args.limit, len(todo))} of {len(todo)} remaining")

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    ok = failed = consecutive = 0
    stopped = False
    for i, p in enumerate(todo[:args.limit]):
        if i:
            time.sleep(random.uniform(*args.delay))
        article = p["article_number"]
        try:
            status, code, size, note = download(session, article)
        except Stop as e:
            log(article, "stopped", "", 0, str(e))
            print(f"STOPPED at {article}: {e}")
            stopped = True
            break
        except requests.RequestException as e:
            status, code, size, note = "failed", "", 0, type(e).__name__
        log(article, status, code, size, note)
        print(f"[{i + 1}] {article} {status} {size // 1024} KB {note}")

        if status == "ok":
            ok, consecutive = ok + 1, 0
        else:
            failed, consecutive = failed + 1, consecutive + 1
            if consecutive >= MAX_CONSECUTIVE_FAILURES:
                print(f"STOPPED: {consecutive} consecutive failures")
                stopped = True
                break

    done = sum(is_pdf(PDF_DIR / f"{p['article_number']}.pdf") for p in papers)
    print(f"\nThis run: {ok} downloaded, {failed} failed. "
          f"Total: {done} of {len(papers)} PDFs in {PDF_DIR.relative_to(ROOT)}")
    sys.exit(1 if stopped or failed else 0)


if __name__ == "__main__":
    main()

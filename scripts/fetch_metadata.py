"""Fetch metadata for every paper in the volumes listed in config/volumes.json.

Pages through each volume 25 records at a time (sorted by article number so
pages are stable across runs), classifies each record as a paper, front
matter to exclude, or a borderline case for review, and writes:

    data/index_all.csv   every record, with status and reason
    data/index.csv       papers only (status == paper)

Responses are cached by xplore.py, so rerunning after hitting the daily cap
resumes where it left off without re-spending calls.
"""

import csv
import json
import re

import xplore

VOLUMES = xplore.ROOT / "config" / "volumes.json"
OUT_ALL = xplore.DATA / "index_all.csv"
OUT = xplore.DATA / "index.csv"

# Titles of non-paper items that appear in proceedings and special issues.
FRONT_MATTER = re.compile(
    r"^(message from|welcome (message|from)|keynote|table of contents?|contents$|"
    r"author index|copyright|(half )?title page|\[|(front |back )?cover$|"
    r"preface$|foreword$|introducing the (ieee|special issue)|"
    r"(program |organizing |steering )?committee|sponsors|supporters|panel|"
    r"tutorial|doctoral consortium|ieee visualization and graphics technical committee|"
    r"conference (organization|committee)|organizers)"
    r"|\b(committees?|reviewers|award winners?|best paper awards?)\s*$",
    re.IGNORECASE,
)
ROMAN = re.compile(r"^[ivxlcdm]+$", re.IGNORECASE)
MIN_PAGES = 4  # shorter items are flagged for review rather than dropped

FIELDS = ["year", "venue", "type", "status", "reason", "article_number", "doi",
          "title", "first_author", "last_author", "n_authors", "authors",
          "start_page", "end_page", "n_pages", "publication_title", "volume",
          "issue", "access_type", "pdf_url"]


def fetch_volume(filt):
    """Return all records for one volume, or raise BudgetExhausted."""
    records, start = {}, 1
    while True:
        d = xplore.search(**filt, start_record=start,
                          sort_field="article_number", sort_order="asc")
        total = int(d.get("total_records", 0))
        for a in d.get("articles", []):
            records[a["article_number"]] = a
        start += xplore.MAX_RECORDS
        if start > total:
            break
    if len(records) != total:
        print(f"  WARNING: got {len(records)} unique records, API reports {total}")
    return list(records.values())


def n_pages(a):
    try:
        return int(a["end_page"]) - int(a["start_page"]) + 1
    except (KeyError, ValueError):
        return None


def classify(a):
    title = a.get("title", "").strip()
    pages = n_pages(a)
    # Checked 2026-09-24: every author-less record was front matter (editorials,
    # committee lists, awards, keynotes, tables of contents, author indexes).
    if not a.get("authors", {}).get("authors"):
        return "excluded", "no authors"
    # IEEE paginates front matter in Roman numerals.
    if ROMAN.match(str(a.get("start_page", ""))):
        return "excluded", "roman-numeral pages"
    if FRONT_MATTER.search(title):
        if pages is not None and pages >= MIN_PAGES:
            return "review", "front-matter title but paper length"
        return "excluded", "front-matter title"
    # Checked 2026-09-24: all 1-2 page authored items were award citations or
    # short invited pieces; the shortest real paper is 5 pages.
    if pages is not None and pages <= 2:
        return "excluded", f"{pages} page(s)"
    if pages is not None and pages < MIN_PAGES:
        return "review", f"{pages} page(s)"
    return "paper", ""


def row(vol, a):
    authors = sorted(a.get("authors", {}).get("authors", []),
                     key=lambda x: int(x.get("author_order", 0)))
    names = [x.get("full_name", "") for x in authors]
    status, reason = classify(a)
    return {
        "year": vol["year"], "venue": vol["venue"], "type": vol["type"],
        "status": status, "reason": reason,
        "article_number": a.get("article_number"), "doi": a.get("doi", ""),
        "title": a.get("title", "").strip(),
        "first_author": names[0] if names else "",
        "last_author": names[-1] if names else "",
        "n_authors": len(names), "authors": "; ".join(names),
        "start_page": a.get("start_page", ""), "end_page": a.get("end_page", ""),
        "n_pages": n_pages(a) or "",
        "publication_title": a.get("publication_title", ""),
        "volume": a.get("volume", ""), "issue": a.get("issue", ""),
        "access_type": a.get("access_type", ""), "pdf_url": a.get("pdf_url", ""),
    }


def write(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def main():
    volumes = json.loads(VOLUMES.read_text())["volumes"]
    rows, incomplete = [], []
    for vol in volumes:
        label = f"{vol['year']} {vol['venue']} {vol['type']}"
        try:
            records = fetch_volume(vol["filter"])
        except xplore.BudgetExhausted:
            incomplete.append(label)
            continue
        vol_rows = [row(vol, a) for a in records]
        rows += vol_rows
        counts = {s: sum(r["status"] == s for r in vol_rows) for s in ("paper", "excluded", "review")}
        print(f"{label:28s} records {len(records):4d}  papers {counts['paper']:4d}  "
              f"excluded {counts['excluded']:3d}  review {counts['review']:3d}")

    rows.sort(key=lambda r: (r["year"], r["venue"], r["type"], int(r["article_number"])))
    write(OUT_ALL, rows)
    write(OUT, [r for r in rows if r["status"] == "paper"])

    print(f"\n{sum(r['status'] == 'paper' for r in rows)} papers -> {OUT.relative_to(xplore.ROOT)}")
    print(f"{len(rows)} records (all statuses) -> {OUT_ALL.relative_to(xplore.ROOT)}")
    if incomplete:
        print(f"\nBudget exhausted; {len(incomplete)} volume(s) not fetched: "
              + ", ".join(incomplete) + "\nRerun after the 24-hour window frees up calls.")
    print(f"budget remaining (24h): {xplore.remaining_budget()}")


if __name__ == "__main__":
    main()

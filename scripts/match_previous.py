"""Match the previous paper's hand-coded VR 2015-2019 papers to Xplore records.

Reads data/IEEEVR2015-2019.xlsx (one row per study) and
data/index_2015-2019_all.csv (from fetch_metadata.py), and writes
data/index_2015-2019_test.csv: one row per old paper with its Xplore record,
plus old_title, old_type and match_score. Invited papers are dropped. Old
titles were altered (underscores for commas, odd spacing), so titles are
compared with punctuation and spaces stripped, then fuzzily within the same
year and track; each Xplore record may be matched only once.

    uv run scripts/match_previous.py
"""

import csv
import difflib
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter

import xplore

OLD = xplore.DATA / "IEEEVR2015-2019.xlsx"
NEW = xplore.DATA / "index_2015-2019_all.csv"
OUT = xplore.DATA / "index_2015-2019_test.csv"

# Papers missing from the old coding, confirmed by a collaborator 2026-10-13.
ADDED = {"8798247"}
MIN_SCORE = 0.6
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def read_xlsx(path):
    """First sheet as a list of dicts keyed by the header row (stdlib only)."""
    z = zipfile.ZipFile(path)
    strings = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        strings = ["".join(si.itertext()) for si in root.findall("m:si", NS)]
    rows = []
    for r in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(f"{{{NS['m']}}}row"):
        row = {}
        for c in r.findall("m:c", NS):
            col = re.match(r"[A-Z]+", c.get("r")).group()
            v, t = c.find("m:v", NS), c.get("t")
            if t == "inlineStr":
                row[col] = "".join(c.itertext())
            elif v is None:
                row[col] = ""
            else:
                row[col] = strings[int(v.text)] if t == "s" else v.text
        rows.append(row)
    header = rows[0]
    return [{header.get(k, k): v for k, v in r.items()} for r in rows[1:]]


def norm(title):
    return re.sub(r"[^a-z0-9]", "", title.lower())


def main():
    old = {}
    for r in read_xlsx(OLD):
        if r["type"] != "invited":
            old.setdefault((r["year"], norm(r["title"])), r)
    new = [r for r in csv.DictReader(open(NEW)) if r["status"] != "excluded"]

    out, used = [], Counter()
    for (year, title), o in old.items():
        cands = {norm(r["title"]): r for r in new
                 if r["year"] == year and (r["type"] == "Journal") == (o["type"] == "tvcg")}
        m = difflib.get_close_matches(title, list(cands), n=1, cutoff=MIN_SCORE)
        if not m:
            sys.exit(f"no match: {year} {o['title']}")
        r = dict(cands[m[0]], old_title=o["title"], old_type=o["type"],
                 match_score=round(difflib.SequenceMatcher(None, title, m[0]).ratio(), 2))
        out.append(r)
        used[r["article_number"]] += 1
    for r in new:
        if r["article_number"] in ADDED:
            out.append(dict(r, old_title="", old_type="", match_score=""))
            used[r["article_number"]] += 1
    dups = [a for a, n in used.items() if n > 1]
    if dups:
        sys.exit(f"Xplore records matched more than once: {dups}")

    out.sort(key=lambda r: (r["year"], r["type"], int(r["article_number"])))
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    print(f"{len(out)} papers -> {OUT.relative_to(xplore.ROOT)}")
    for (year, typ), n in sorted(Counter((r["year"], r["type"]) for r in out).items()):
        print(f"  {year} {typ:10s} {n}")
    for r in out:
        if r["match_score"] != "" and r["match_score"] < 0.9:
            print(f"  check: {r['article_number']} score {r['match_score']}\n"
                  f"    old: {r['old_title']}\n    new: {r['title']}")


if __name__ == "__main__":
    main()

"""Find the Xplore IDs of each in-scope volume, for review before the full pull.

Conference track: the main proceedings' publication_number for each venue/year
(adjunct, workshop and abstract volumes are excluded).
Journal track: the is_number of the TVCG issue(s) matching each venue/year.

Prints candidates with record counts; the reviewed result goes in
config/volumes.json. Costs about 2 API calls per venue per year (one more
per extra title).

    uv run scripts/discover_volumes.py                         # 2020+, both venues
    uv run scripts/discover_volumes.py --venue "IEEE VR" 2015 2016 2017 2018 2019
"""

import argparse
from collections import Counter

import xplore

YEARS = range(2020, 2027)
TVCG = 2945

# Proceedings titles to search. IEEE VR was "IEEE Virtual Reality (VR)" until
# 2017 and "Conference on Virtual Reality and 3D User Interfaces" from 2018.
VENUES = {
    "IEEE VR": {"titles": ["Virtual Reality and 3D User Interfaces", "IEEE Virtual Reality"],
                "topic": "virtual reality"},
    "ISMAR": {"titles": ["Mixed and Augmented Reality"], "topic": "augmented reality"},
}
EXCLUDE = ("Adjunct", "Abstracts", "Workshop")


def conference_candidates(title, year):
    d = xplore.search(publication_title=title, publication_year=year)
    seen = Counter((a["publication_number"], a["publication_title"]) for a in d.get("articles", []))
    return d.get("total_records", 0), seen


def tvcg_candidates(venue, year):
    d = xplore.search(publication_number=TVCG, publication_year=year,
                      querytext=VENUES[venue]["topic"])
    seen = Counter((a["is_number"], a.get("volume"), a.get("issue"))
                   for a in d.get("articles", []))
    return d.get("total_records", 0), seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("years", nargs="*", type=int, default=list(YEARS))
    ap.add_argument("--venue", choices=VENUES, action="append",
                    help="limit to this venue (repeatable); default all")
    args = ap.parse_args()
    for year in args.years:
        for venue in args.venue or VENUES:
            try:
                for search_title in VENUES[venue]["titles"]:
                    total, seen = conference_candidates(search_title, year)
                    print(f"\n{year} {venue} conference, title \"{search_title}\" "
                          f"(search total {total}):")
                    for (pn, title), n in seen.most_common():
                        flag = "  [excluded]" if any(x in title for x in EXCLUDE) else ""
                        print(f"  pub={pn}  x{n}  {title}{flag}")
                total, seen = tvcg_candidates(venue, year)
                print(f"{year} {venue} TVCG issues (search total {total}):")
                for (isn, vol, iss), n in seen.most_common():
                    print(f"  is={isn}  vol {vol} issue {iss}  x{n}")
            except xplore.BudgetExhausted as e:
                print(e)
                return
    print(f"\nbudget remaining (24h): {xplore.remaining_budget()}")


if __name__ == "__main__":
    main()

"""Find the Xplore IDs of each in-scope volume, for review before the full pull.

Conference track: the main proceedings' publication_number for each venue/year
(adjunct, workshop and abstract volumes are excluded).
Journal track: the is_number of the TVCG issue(s) matching each venue/year.

Prints candidates with record counts; the reviewed result goes in
config/volumes.json. Costs about 2 API calls per venue per year.
"""

import sys
from collections import Counter

import xplore

YEARS = range(2020, 2027)
TVCG = 2945

VENUES = {
    "IEEE VR": {"title": "Virtual Reality and 3D User Interfaces", "topic": "virtual reality"},
    "ISMAR": {"title": "Mixed and Augmented Reality", "topic": "augmented reality"},
}
EXCLUDE = ("Adjunct", "Abstracts", "Workshop")


def conference_candidates(venue, year):
    d = xplore.search(publication_title=VENUES[venue]["title"], publication_year=year)
    seen = Counter((a["publication_number"], a["publication_title"]) for a in d.get("articles", []))
    return d.get("total_records", 0), seen


def tvcg_candidates(venue, year):
    d = xplore.search(publication_number=TVCG, publication_year=year,
                      querytext=VENUES[venue]["topic"])
    seen = Counter((a["is_number"], a.get("volume"), a.get("issue"))
                   for a in d.get("articles", []))
    return d.get("total_records", 0), seen


def main():
    years = [int(y) for y in sys.argv[1:]] or YEARS
    for year in years:
        for venue in VENUES:
            try:
                total, seen = conference_candidates(venue, year)
                print(f"\n{year} {venue} conference (search total {total}):")
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

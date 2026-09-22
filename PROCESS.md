# Process: Extracting Participant-Demographics Data from IEEE VR & ISMAR Papers

## Goal

Build a structured dataset covering every paper published at/through **IEEE VR** (conference track + journal track) and **ISMAR** (conference track + journal track) **from 2020 onward**, extracting bibliographic info plus user-study participant demographics (counts, gender breakdown, age stats). The end goal is to analyze reporting practices and representation (e.g., gender balance, age range) in VR/AR human-subjects research over time.

## 1. Scope & Sources

**Time range: 2020–present.** Earlier years are out of scope for this pass.

| Venue | Conference track | Journal track |
|---|---|---|
| **IEEE VR** | IEEE Conference on Virtual Reality and 3D User Interfaces, proceedings papers | Papers accepted via the VR journal track, published in **IEEE TVCG** (Transactions on Visualization and Computer Graphics), presented at IEEE VR |
| **ISMAR** | ISMAR proceedings | Papers accepted via the ISMAR journal track, published in **IEEE TVCG**, presented at ISMAR |

Both venues route their "journal track" through TVCG, so `Type` must be determined per-paper from the submission track, not just the outlet name — TVCG issues around VR/ISMAR week contain a mix that must be disambiguated using the conference program / TVCG special-issue table of contents.

**Primary sources for retrieval:**
- [IEEE Xplore](https://ieeexplore.ieee.org/) — canonical source for conference proceedings and TVCG; has an API and per-issue/per-conference browse pages.
- [dblp](https://dblp.org/) — clean, structured bibliographic listings per venue/year (`dblp.org/db/conf/vr/`, `dblp.org/db/conf/ismar/`, `dblp.org/db/journals/tvcg/`), good for building the initial paper list (title, authors, year) before pulling full text.
- Conference program PDFs / TOCs — needed to determine conference-vs-journal-track split for a given year, and to get final author order and presentation format.
- Publisher/author PDFs (IEEE Xplore, author websites, ResearchGate, arXiv preprints) — needed for full-text extraction of study details (participants, demographics).

## 2. Retrieval Process

> **Note on IEEE Xplore access:** Claude cannot authenticate to IEEE Xplore's normal browser/SSO-based access itself (no browser session, and web-fetch tools do not run from the user's institutional network/VPN, so IP-based access does not carry over). That access is used *manually* by the user at two points below (steps 1 and 3) — Xplore's own export/download features — with the resulting files handed to Claude to process. **Exception:** if the user's institution has a separate **Text & Data Mining (TDM) API agreement** with IEEE (distinct from the ordinary read subscription — check with the library), Claude *can* call that API directly via `curl` (Bash), using the issued API key, for both metadata and full text. That would replace the manual steps below with a scripted pull. Preferred order: TDM API (if available) > manual export/download (fallback).

1. **Build the paper index per venue/year.** Options, in preferred order:
   - *TDM API (if institution has an agreement)*: script queries per venue/year directly against the IEEE Xplore TDM API, returning metadata (and full text) in one pass — no manual export needed.
   - *No login needed*: dblp listings for `conf/vr`, `conf/ismar`, and `journals/tvcg` (filtered to VR/ISMAR-track issues).
   - *Manual institutional access*: run a scoped search on IEEE Xplore per venue/year and use "Export Results" (CSV/BibTeX/RIS, up to 2000 records per export); share the export file for processing.
   Record: year, venue, title, author list (in order), DOI/Xplore link.
2. **Classify Type (conference/journal)** per paper using the conference program or TVCG TOC annotation (TVCG explicitly marks papers as "presented at IEEE VR 20XX" or "presented at ISMAR 20XX").
3. **Retrieve full text.** With TDM API access, pull full text directly via the API. Otherwise, download PDFs via IEEE Xplore (manual institutional access) into a local folder, or via author-hosted copies where Xplore access isn't available; Claude reads PDFs directly from that folder.
4. **Screen for a user study**: search the PDF for a "Participants," "User Study," "Evaluation," or "Method(s)" section describing human subjects. Papers with no human-subject evaluation (e.g., purely technical/systems papers, simulation-only) are marked `Has user study: No` and all downstream participant fields are marked **NA**.
5. **Extract demographics** from the identified section(s) (see schema below) directly into the dataset.
6. **Spot-check / QC** a random sample (e.g., 10%) with a second reader to check extraction accuracy, since demographic reporting is inconsistently located and phrased across papers.

## 3. Data Schema

One row per paper.

| Field | Notes |
|---|---|
| Year | Publication year (conference presentation year for journal-track papers, to keep it aligned with the venue-year the paper "belongs to") |
| Venue | `IEEE VR` or `ISMAR` — which conference the paper belongs to, regardless of track |
| Type | `Conference` or `Journal` |
| Title | Full paper title |
| First author | As listed on the paper |
| Last author | As listed on the paper (senior/PI author by convention, if distinguishable from "second author" in a 2-author paper) |
| Total authors | Integer count |
| Has user study | `Yes` / `No` — whether the paper involved human participants |
| Total participants | Integer; **NA** if no study or count not reported |
| Female participants | As reported by authors' own terminology; **NA** if not reported |
| Male participants | As reported by authors' own terminology; **NA** if not reported |
| Other participants | Non-binary / other / undisclosed / prefer-not-to-say, summed; **NA** if not reported |
| Other descriptors | Free text, e.g., "non-binary," "prefer not to say," "other," "genderqueer" — copy authors' own labels verbatim; **NA** if no such category reported |
| Min age | As reported; **NA** if not reported |
| Max age | As reported; **NA** if not reported |
| Mean age | As reported; **NA** if not reported |
| Age SD | As reported; **NA** if not reported |

Any field the paper does not report gets the literal string **NA** — never a blank cell and never `0` (a blank/0 is ambiguous between "not reported" and "reported as zero"). This applies to every field above except Year, Venue, Type, Title, First/Last author, and Total authors, which should always be extractable from the paper itself.

### Extraction rules / edge cases
- **Use authors' own terminology** for gender categories rather than normalizing; keep a separate "descriptors" field to preserve nuance (some papers use "sex," some "gender," some conflate the two — note this ambiguity in a comments column if needed).
- **Missing data stays missing** — do not infer or estimate; mark it **NA** rather than guessing. If a paper reports total N and % female but not raw counts, compute raw counts and note the derivation; if age is reported only as a range (no mean/SD) or only as mean (no range), fill in only what's given and mark the rest **NA**.
- **Multiple studies in one paper**: record aggregated totals across all studies by default, and consider a `notes` column flagging multi-study papers for later disaggregation if needed.
- **Within-subjects/between-subjects or multiple conditions**: participant count = unique individuals, not condition-participation instances.
- **No demographics reported at all** but a study clearly involved human participants: still mark `Has user study: Yes`, fill total N if available, mark gender/age fields **NA** rather than `0`.

## 4. Suggested Tooling

- **Check for TDM API access first** — ask the library/research-support office whether the institution has a Text & Data Mining agreement with IEEE (separate from the regular read/download subscription). If so, this is the preferred path: a scripted `curl`-based (Bash) pull against the TDM API, using the issued key, for both metadata and full text — replacing the manual export/download steps and the ad hoc dblp cross-check.
- Note: the ordinary free IEEE Xplore Metadata API (`developer.ieee.org`) is a separate, individual-account API key and only returns metadata (title, authors, abstract, DOI) — no full text — so it doesn't help with the demographics extraction itself, only the bibliographic index.
- If no TDM access: script the dblp → paper-index step (dblp provides XML/JSON exports per venue), and use the manual Xplore export/download route in §2 for full text.
- PDF text extraction (e.g., `pdftotext`, or a PDF-parsing library) to pull candidate "Participants" sections automatically as a first pass, followed by manual/LLM-assisted verification given how inconsistently this information is reported.
- Store the working dataset as CSV/spreadsheet (one row per paper) for downstream analysis (e.g., trends over time in gender balance, reporting completeness).

## 5. Known Limitations

- Scoped to 2020–present, so full-text access should be uniformly available via IEEE Xplore given institutional access, once PDFs are manually downloaded (see §2 note); digitization gaps are not expected to be an issue at this recency.
- Demographic reporting norms still vary within 2020–present (non-binary/other categories are more common than in earlier years but still inconsistently reported), so absence of an "other" count doesn't necessarily mean an all-binary participant pool.
- Determining "last author" as the senior/PI author is a convention, not a guarantee — some subfields/labs order authors alphabetically or by contribution instead.

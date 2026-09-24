# Process: Extracting Participant-Demographics Data from IEEE VR & ISMAR Papers

## Goal

Build a structured dataset covering every paper published at/through **IEEE VR** (conference track + journal track) and **ISMAR** (conference track + journal track) **from 2020 onward**, extracting bibliographic info plus user-study participant demographics (counts, gender breakdown, age stats). The end goal is to analyze reporting practices and representation (e.g., gender balance, age range) in VR/AR human-subjects research over time.

## 1. Scope & Sources

**Time range: 2020–present.** Earlier years are out of scope for this pass.

| Venue | Conference track | Journal track |
|---|---|---|
| **IEEE VR** | IEEE Conference on Virtual Reality and 3D User Interfaces, proceedings papers | Papers accepted via the VR journal track, published in **IEEE TVCG** (Transactions on Visualization and Computer Graphics), presented at IEEE VR |
| **ISMAR** | ISMAR proceedings | Papers accepted via the ISMAR journal track, published in **IEEE TVCG**, presented at ISMAR |

Both venues route their "journal track" through TVCG, so `Type` can't be read from the outlet name alone. It is determined by the volume: each conference's journal-track papers are published together in a dedicated TVCG special issue (see §2, step 1), and regular TVCG issues are out of scope even when they contain VR/AR papers. Adjunct, workshop, poster and abstract volumes (ISMAR-Adjunct, IEEE VR Abstracts & Workshops) are also out of scope.

**Primary sources for retrieval:**
- [IEEE Xplore](https://ieeexplore.ieee.org/) — canonical source for conference proceedings and TVCG; has an API and per-issue/per-conference browse pages.
- [dblp](https://dblp.org/) — clean, structured bibliographic listings per venue/year (`dblp.org/db/conf/vr/`, `dblp.org/db/conf/ismar/`, `dblp.org/db/journals/tvcg/`). **As of 2026-09-24, all of dblp (HTML pages, XML exports and the search API) sits behind an automated bot challenge**, so it can't be scripted. It's still usable in a browser for manual spot-checks.
- Conference program PDFs / TOCs — needed to determine conference-vs-journal-track split for a given year, and to get final author order and presentation format.
- Publisher/author PDFs (IEEE Xplore, author websites, ResearchGate, arXiv preprints) — needed for full-text extraction of study details (participants, demographics).

## 2. Retrieval Process

> **Note on IEEE Xplore access (confirmed):** the institution has approved IEEE Xplore API access for this project, with these terms:
> - **200 API calls per day, max 25 records per call** (~5,000 metadata records/day). The key itself reports limits of 210 calls/day and 10 calls/second; the scripts cap at 200 per rolling 24 hours to leave a margin.
> - The API returns **metadata only**. Full text is obtained by harvesting each record's PDF URL (`pdf_url`) from the metadata and downloading the PDF in a separate step.
>
> The key is stored in `.env` (as `IEEE_XPLORE_API_KEY`), which is gitignored and must never be committed.
>
> Claude's `Bash` tool runs on the user's own machine, so requests go out from the user's network. PDF access is IP-based: it works only from an address inside the institution's IEEE subscription. WebFetch does *not* run from the user's network, so it can't be used for PDFs. See step 3 for which networks have been tested.

1. **Build the paper index per venue/year** using the IEEE Xplore Metadata API (`https://ieeexploreapi.ieee.org/api/v1/search/articles`). This happens in two parts.

   **1a. Identify the in-scope volumes** *(done 2026-09-24, 46 API calls; `scripts/discover_volumes.py`)*. Every in-scope volume has an Xplore ID that the API can filter on exactly:
   - *Conference track*: the main proceedings' `publication_number`. A plain `publication_title` search returns a mix of main, adjunct and workshop volumes, and the adjunct/workshop records often crowd the main proceedings out of the first page. A boolean query that excludes them finds the main volume reliably, e.g. `querytext=("Publication Title":"Mixed and Augmented Reality" NOT "Publication Title":Adjunct)` with `publication_year`.
   - *Journal track*: the TVCG special issue's `is_number` (issue ID). The API ignores an `issue` parameter, but `is_number` works as a filter. Special issues were found by searching TVCG (`publication_number=2945`) per year. Each ISMAR special issue was then confirmed by its guest-editor message ("Message from the ISMAR 20XX … Program Chairs and TVCG Guest Editors"). VR special issues were identified by issue 5 dominating VR-related results every year.

   The results are in `config/volumes.json`: 26 volumes, summarized below. ISMAR 2026 hasn't taken place yet; rerun discovery for it once its volumes appear on Xplore.

   | Venue | Conference track | Journal track (TVCG) |
   |---|---|---|
   | IEEE VR 2020–2026 | Main proceedings, 7 volumes | Issue 5 each year (vol. 26–32) |
   | ISMAR 2020–2025 | Main proceedings, 6 volumes | Issue 12 in 2020 (vol. 26); issue 11 in 2021–2025 (vol. 27–31) |

   **1b. Fetch every paper in each volume** *(done 2026-09-24, 103 API calls; `scripts/fetch_metadata.py`)*. Each volume's filter is queried in pages of 25, sorted by article number so page boundaries stay stable across runs, and the unique record count is checked against the API's reported total. The 2,320 raw records are then classified by these rules, applied in order and each checked by hand against the records it catches:
   1. **No authors → excluded** (279): committee lists, sponsor pages, tables of contents, author indexes, award citations, keynote abstracts.
   2. **Roman-numeral page numbers → excluded** (49): IEEE paginates front matter this way, e.g. chairs' messages and awards that list their signers as authors.
   3. **Front-matter title pattern → excluded** (8), e.g. "Message from…", "Keynote Speaker…". If such a record is paper-length (4+ pages), it's flagged for review instead, so a real paper whose title happens to begin "Introducing…" or "Welcome…" isn't lost. Four such papers were caught this way in an earlier version of the rule.
   4. **1–2 pages → excluded** (4): award citations and a short invited piece. The shortest real paper is 5 pages.

   **Result: 1,980 papers** in `data/index.csv` (all 2,320 records with status and reason are in `data/index_all.csv`). No papers are left for review; none is missing page numbers, authors or a `pdf_url`; there are no duplicate article numbers or DOIs; paper lengths run 5–14 pages. 109 papers are open access (CC BY or `OPEN_ACCESS`), and the other 1,871 are `LOCKED`, i.e. subscription access is needed for the PDF.

   | Papers | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
   |---|---|---|---|---|---|---|---|
   | IEEE VR conference | 104 | 92 | 90 | 69 | 101 | 75 | 68 |
   | IEEE VR journal | 29 | 25 | 29 | 61 | 79 | 136 | 160 |
   | ISMAR conference | 69 | 56 | 93 | 128 | 133 | 157 | — |
   | ISMAR journal | 18 | 24 | 35 | 45 | 44 | 60 | — |

   **Completeness check:** since dblp can't be scripted (§1), compare each volume's paper count against its Xplore table-of-contents page or the conference program.

   *Fallback (manual)*: run a scoped search on IEEE Xplore per venue/year and use "Export Results" (CSV/BibTeX/RIS, up to 2000 records per export); share the export file for processing.
2. **Classify Type (conference/journal)** from the volume each paper came from (conference proceedings → `Conference`; TVCG special issue → `Journal`). No per-paper disambiguation is needed.
3. **Retrieve full text** with `scripts/download_pdfs.py` into `data/pdfs/<article_number>.pdf`. For each paper it fetches the `stamp.jsp` page, which sets session cookies and reveals whether the network is entitled, then follows its iframe to the real PDF. A file is saved only if it starts with `%PDF`. Politeness rules, since bulk automated downloading can get the whole institution's IP range blocked: one request at a time, a random 5–10 s pause between papers, at most 300 papers per run by default, an immediate stop on a login redirect or on HTTP 403/418/429, and a stop after 5 consecutive failures. Reruns skip files already downloaded, and every attempt is logged to `data/logs/downloads.csv`. Requests use an honest identifier (`research-pdf-harvest`), not a spoofed browser. For any paper Xplore can't serve, fall back to author-hosted copies or arXiv.

   **Open-access papers (109)** download from any network. **Subscription papers (1,871)** need a network that IEEE recognizes as part of UNC's subscription. As of 2026-09-24, none of the networks tried so far qualifies:

   | Network | Result |
   |---|---|
   | Home connection, and UNC VPN `Telemed` group | Split tunnel: only UNC address ranges go through the VPN, and Xplore (served via Amazon CloudFront) doesn't. It exits via the home ISP, so Xplore redirects to login. |
   | UNC VPN `Full-Tunnel` and `Library` groups | Sign-in succeeds, then the gateway rejects the account ("Authentication failed", plus "VPN Server internal error" for Full-Tunnel), i.e. the account isn't authorized for these groups. |
   | RENCI server over SSH | Leaves via `AS81 MCNC`, not UNC's own address space. Xplore redirects to login (`authDecision=-203`). |

   **Open:** find an entitled network. Options are a machine in UNC's own address space (e.g. a UNC Research Computing server), ITS granting access to the Library or Full-Tunnel VPN group, or the library/approver advising the intended route (possibly adding RENCI's range to the subscription).

   *Implementation note:* IPv6 connections to Xplore's CDN hung from the user's network, so the script uses IPv4 only.
4. **Screen for a user study**: search the PDF for a "Participants," "User Study," "Evaluation," or "Method(s)" section describing human subjects. Papers with no human-subject evaluation (e.g., purely technical/systems papers, simulation-only) are marked `Has user study: No` and all downstream participant fields are marked **NA**.
5. **Extract demographics** from the identified section(s) (see schema below) directly into the dataset.
6. **Spot-check / QC** a random sample (e.g., 10%) with a second reader to check extraction accuracy, since demographic reporting is inconsistently located and phrased across papers.

### Planned implementation of steps 4–6 *(proposed 2026-09-24; not started, decisions pending)*

To be piloted on the 109 open-access PDFs already downloaded, then run on the rest.

1. **Convert each PDF to text** (`scripts/extract_text.py` → `data/text/<article_number>.txt`) with PyMuPDF (`pip install pymupdf`), which handles IEEE's two-column layout well. No PDF text tool is installed yet.
2. **Find the relevant passages** (`scripts/find_candidates.py`): keyword search for participant language ("participants", "recruited", "N =", "female", "male", "non-binary", "aged", "M =", "SD =", "years old", "demographic"), keeping a window of text around each hit. Papers with no hits become *candidates* for `Has user study: No`, confirmed in the next step rather than set automatically. This cuts the text per paper from ~10 pages to ~1.
3. **Extract the details** (`scripts/extract_demographics.py`): Claude reads each paper's passages and fills in the §3 fields as structured JSON. Every value must come with the **exact quote** it came from.
4. **Automatic checks** on every result; anything failing goes to a review list rather than into the dataset:
   - each quote appears word-for-word in the paper's text (catches invented values)
   - female + male + other = total
   - minimum age ≤ mean ≤ maximum, and ages are plausible
   - a stated total matches the per-study numbers
5. **Pilot and quality check**: the user hand-codes ~20 open-access papers as a reference set, and the extraction instructions are adjusted until they agree. Then the 10% second-reader check (step 6 above) on the full set.

**Open decision: how the extraction step runs.**
- *(Recommended)* A script calling the Claude API: reproducible and rerunnable, with every result logged next to its quotes, which suits a methods section. Needs an Anthropic API key in `.env` and costs per paper; check current pricing before estimating.
- Subagents in a Claude Code session: no key or separate billing, but harder to rerun identically and slower for ~2,000 papers.

**Open rules, to settle before the pilot** (proposed defaults in italics). These change the numbers, so they belong in the methods:
1. **Multiple studies in one paper**: *one row per study in a second table, plus a paper-level total that adds up studies only when the paper says the participants were different people; otherwise flagged.* This supersedes "aggregate across studies" in the extraction rules below.
2. **Recruited vs. analyzed participants**: *record the analyzed count, with exclusions in the notes* (demographics are often reported for the recruited group; the note makes that visible).
3. **Pilot, expert-only and crowdsourced studies**: *count all as user studies, with a column recording which kind, so they can be filtered later.*
4. **Gender vs. sex wording**: *record the paper's own term (gender / sex / unclear) in a column*, per the terminology rule below.

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

## 4. Tooling

All scripts are Python 3 (standard library plus `requests`) and live in `scripts/`.

| Script / file | Status | Purpose |
|---|---|---|
| `scripts/xplore.py` | Done | Shared API client. Reads the key from `.env`, caches every successful response in `data/raw/api/` (keyed by the query parameters, so a query is never paid for twice), logs call times in `data/api_calls.json`, stops at 200 calls per rolling 24 hours, and spaces calls ≥0.5 s apart. Also usable as a one-off probe: `python3 scripts/xplore.py publication_number=9583730`. |
| `scripts/discover_volumes.py` | Done | Step 1a: lists candidate volumes per venue/year with hit counts. Only needed again when new volumes appear (e.g. ISMAR 2026). |
| `config/volumes.json` | Done | The reviewed list of 26 in-scope volumes and their Xplore filters (committed, so the scope is auditable). |
| `scripts/fetch_metadata.py` | Done | Step 1b: pages through each volume, filters out front matter, writes `data/index.csv` (papers) and `data/index_all.csv` (all records with status/reason). Rerunning is free once responses are cached. |
| `scripts/download_pdfs.py` | Done; blocked on network for subscription papers | Step 3 (see above): throttled, resumable PDF download. `--open-access-only` limits it to papers that need no subscription; `--limit N` caps a run (default 300). |

`data/` (API cache, call log, index, PDFs) is gitignored: it's reproducible from the scripts, and the PDFs are copyrighted.

Later stages:
- PDF text extraction (e.g., `pdftotext`, or a PDF-parsing library) to pull candidate "Participants" sections automatically as a first pass, followed by manual/LLM-assisted verification given how inconsistently this information is reported.
- Store the working dataset as CSV/spreadsheet (one row per paper) for downstream analysis (e.g., trends over time in gender balance, reporting completeness).

## 5. Known Limitations

- Scoped to 2020–present, so full-text access should be uniformly available via IEEE Xplore given institutional access, via the harvested `pdf_url`s (see §2 step 3); digitization gaps are not expected to be an issue at this recency.
- Demographic reporting norms still vary within 2020–present (non-binary/other categories are more common than in earlier years but still inconsistently reported), so absence of an "other" count doesn't necessarily mean an all-binary participant pool.
- Determining "last author" as the senior/PI author is a convention, not a guarantee — some subfields/labs order authors alphabetically or by contribution instead.

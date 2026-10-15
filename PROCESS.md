# Process: Extracting Participant-Demographics Data from IEEE VR & ISMAR Papers

## Goal

Build a structured dataset covering every paper published at/through **IEEE VR** (conference track + journal track) and **ISMAR** (conference track + journal track) **from 2020 onward**, plus IEEE VR 2015–2019 (the previous paper's period, re-extracted), extracting bibliographic info plus user-study participant demographics (counts, gender breakdown, age stats). The end goal is to analyze reporting practices and representation (e.g., gender balance, age range) in VR/AR human-subjects research over time.

## 1. Scope & Sources

**Time range: IEEE VR 2015–present; ISMAR 2020–present** *(decided 2026-10-15)*. The 2015–2019 rows cover IEEE VR only, the same papers as the previous paper's hand-coded dataset (326 papers; see "Previous dataset" in §2), re-extracted with the new pipeline. They also serve as the test set. ISMAR 2015–2019 is not included. ISMAR 2026 is added once its volumes appear on Xplore (see Q32).

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
   - female + male + the non-binary, prefer-not-to-say, not-reported and other counts = total
   - minimum age ≤ mean ≤ maximum, and ages are plausible
   - a stated total matches the per-study numbers
5. **Pilot and quality check**: the user hand-codes ~20 open-access papers as a reference set, and the extraction instructions are adjusted until they agree. Then the 10% second-reader check (step 6 above) on the full set. *A cheaper alternative is under review; see "Proposed validation design" below.*

**Open decision: how the extraction step runs.**
- *(Recommended)* A script calling the Claude API: reproducible and rerunnable, with every result logged next to its quotes, which suits a methods section. Needs an Anthropic API key in `.env` and costs per paper; check current pricing before estimating.
- Subagents in a Claude Code session: no key or separate billing, but harder to rerun identically and slower for ~2,000 papers.

**Counting rules** *(decided 2026-10-13 and 2026-10-15; details in §3)*. These change the numbers, so they belong in the methods:
1. **Multiple studies in one paper**: one row per study, with a Study number column. A separate study means **new participants**; one group doing "two experiments" is one study with two blocks. Each paper with a user study also gets a **Study 0** row: the paper-level total of unique participants it reports, with combined demographics (a copy of Study 1 for single-study papers).
2. **Recruited vs. analyzed participants**: record the analyzed count where possible, with exclusions in the notes, and a Count basis column (recruited / analyzed / unknown) saying which one the row holds.
3. **Pilot, expert-only and crowdsourced studies**: recorded, with a Study type column so they can be filtered. Pilots are not counted as studies in the analysis (the old coding didn't count them).
4. **Gender vs. sex wording**: record the paper's own term (gender / sex / unclear) in a column, per the terminology rule below.
5. **Reused studies** *(decided 2026-10-15)*: participants already counted in another paper in the dataset are recorded but not counted again (Reused from column).
6. **Informal feedback** *(decided 2026-10-15)* counts as a user study, Study type `Informal`.

### Proposed validation design *(proposed 2026-10-12; for review)*

A cheaper alternative to the 10% second-reader check in item 5 above. A 10% check means hand-coding ~200 papers. The design below should take the equivalent of ~50–80 papers' worth of effort and give a finer-grained result: accuracy per field, separate precision and recall, and a measured error rate among values the models agreed on.

Since all 1,980 papers now have full-text XML, the ~20 tuning papers no longer need to be open-access. A sample stratified by venue and year represents the whole set better. Test samples are drawn so they don't include any tuning papers.

**Option A: agreement across different LLMs.** Run the extraction twice, either with models from different families (e.g., Claude plus GPT or Gemini) or with one model and two differently worded prompts. Each field then sorts into one of two groups:
- *Agree*: probably right, but not certainly. Models make correlated mistakes, such as misreading the same ambiguous sentence or missing the same second study.
- *Disagree*: all go to human review. This is error **correction**, not error **measurement**.

To turn this into an accuracy figure, review every disagreement plus a small random sample of agreements:
overall error = P(agree) × error rate among agreements + P(disagree) × error rate among disagreements.
The agreement sample is what keeps the estimate honest. Inter-model agreement (kappa) is also worth reporting in its own right. The costs are a second extraction run and reviewing the disagreements; that queue's size is unknown until the pilot runs.

**Option B: sample fields, not papers.** Because every extracted value comes with its exact quote, checking a single field is quick: read the quote and confirm the value. That takes ~20–30 seconds, versus several minutes to code a whole paper, so (paper, field) pairs can be sampled across many papers. The catch is that quote checks catch **wrong values** but not **missed values**. Examples are a second study that was never extracted, or an "other/non-binary" count reported as absent. Measuring misses means reading the paper's participant section. So the check splits in two:
- *Precision* (is each extracted value correct?): many cheap, quote-based checks.
- *Recall* (did it miss anything?): fewer, but each reads the full participant passage.

`Has user study = No` needs its own small sample, because a wrongly screened-out paper has no quotes to check.

**Option C: stop early as accuracy converges.** Annotate in random order and track each field's accuracy with a confidence interval. Stop once the interval is narrow enough. Reference points:
- *0 errors in n checks*: the 95% upper bound on the error rate is ~3/n (the "rule of three"). 60 clean checks put error at ≤5%, and 100 put it at ≤3%.
- *~97% accuracy*: ±5 points needs ~45 checks, and ±3 points needs ~125.

So if extraction turns out accurate, a field can stop at 40–60 checks. The stopping rule must be written down before starting, e.g., "minimum 30, stop when the 95% Wilson half-width ≤ 5 points, maximum 100." Deciding when to stop by watching the results as they come in biases the estimate.

**Other options.**
- *Oversample the hard cases with weights.* Errors will cluster in multi-study papers, recruited-vs-analyzed mismatches and unusual gender wording. Oversampling those strata and reweighting gives the population estimate while finding more errors per hour of review.
- *Blind vs. assisted review.* Reviewing with the LLM's answer visible is faster but anchors the reviewer toward agreeing. The ~20 blind tuning papers partly cover this. A further ~10–15 blind papers in the test set would show whether assisted review inflates agreement.
- *A second human on a small subset.* If reviewers ask about human–human reliability, ~20 papers coded by a colleague gives a kappa to compare against.

**Recommended combined design.**
1. *Tuning*: ~20 papers, hand-coded blind, as in item 5 above.
2. *Full run with two model families*, plus the automatic checks in item 4. A human reviews the disagreements and check failures. This fixes errors but isn't counted toward accuracy.
3. *Accuracy audit*, with the stopping rule written down beforehand:
   - field-level quote checks on a random sample, stratified by agree/disagree, with the stopping rule above (expect ~40–80 checks per key field)
   - ~30 papers read in full for recall
   - ~30 "No user study" papers skimmed
4. *Report* human–LLM accuracy with confidence intervals for each field, inter-model kappa, and the agree/disagree breakdown.

**To decide:** whether to adopt this in place of the 10% second-reader check; which second model family (or second prompt) to use; the stopping rule's thresholds; and which fields count as "key" for the per-field audit.

### Previous dataset as a test set *(proposed 2026-10-13; for review)*

*Decided 2026-10-15: the re-extracted 2015–2019 data is part of the dataset, not only a test set (Q3).*

`data/IEEEVR2015-2019.xlsx` holds the hand-coded data from the previous paper, which this one follows up. It covers IEEE VR only, 2015–2019: 356 papers in 471 rows, already one row per study with a study number. 70 papers have no user study, and 80 have more than one study (53 with 2, 19 with 3, 8 with 4). By type there are 267 conference, 108 TVCG and 31 "invited" papers (TVCG regular-issue papers presented at VR). *Decided 2026-10-13: the invited papers are dropped*, matching the 2020+ scope, which leaves 325 papers (the per-type study counts above still include them).

The proposal is to fetch these papers' full text, run the new pipeline on them, and compare the output with the old coding. That replaces most of the hand-coding in the validation design above. About 300 papers would be held out for testing, which also measures missed studies (the multi-study papers), the user-study screen (the no-study papers) and missed values.

Caveats:
- **The old labels aren't ground truth.** Disagreements are settled by hand, and some will turn out to be errors in the old coding. Results are reported as agreement with adjudication; as a side benefit, this measures the old dataset's error rate.
- **The counting rules have to match** the old conventions, or the comparison mostly turns up rule differences. Known old conventions (user, 2026-10-13): counts are unknown but probably recruited; a separate study meant new participants; pilots weren't counted; `males`/`females` covered binary categories only, and the only other category in the whole dataset was non-binary. The new Count basis column will show how often recruited and analyzed differ.
- **Study rows have to line up.** Old rows have only a study number. A different number of rows for a paper flags a disagreement about how the paper divides into studies.
- **Older papers may report differently,** and the old data has no columns for gender categories beyond male and female (non-binary was the only other category the old papers reported). A small audit on 2020+ data is still needed, aimed mostly at the new gender columns.
- **Tuning and test papers must stay separate.** Split by paper, stratified by year, type and single vs. multi-study.

Data notes:
- Missing values use three codes, `-`, `?` and `NA`, which all mean NA. Papers with no study have total participants `0`, which is also read as NA. The new extraction uses only `NA`.
- 6 rows have males + females ≠ total. Left for the comparison to sort out.
- Titles have been altered (underscores for commas, doubled or missing spaces, dropped punctuation), so matching them to Xplore needs fuzzy matching.

Schema mapping (old column → new column; agreed 2026-10-15). The comparison script uses this table.

| Old column | New column | Notes |
|---|---|---|
| `year` | Year | |
| `type` | Type | `conference` → Conference, `tvcg` → Journal; `invited` rows dropped |
| `author` | First author | Old holds the surname only; compare surnames |
| `title` | Title | Old titles are altered; compare fuzzily, as in `match_previous.py` |
| `author.male` + `author.female` | Total authors | The sum is the author count. Author gender itself is dropped |
| `human.subjects.study` | Has user study | `1` → Yes, `0` → No |
| `study.number` | Study number | Old numbering starts at 1 with no Study 0, and no-study papers have `1` (two have `2`). Compare against new rows 1, 2, … only |
| `total.participants` | Total participants | Old `0` on no-study papers = NA. Old counts are probably recruited, so compare against Count basis too |
| `females` | Female participants | |
| `males` | Male participants | |
| (none) | Non-binary participants | The old data has one non-binary participant in the whole dataset and no column for it. With so few, the gender comparison uses female and male only |
| `age.min`, `age.max` | Min age, Max age | |
| `age.avg` | Mean age | |
| `age.SD` | Age SD | |
| `first.author.gender`, `session`, `category` | (dropped) | Keywords replace session and category (decided 2026-10-13), and are collected for the 2015–2019 papers too |

New-schema fields with no old counterpart (can't be compared): Last author, DOI, keywords, Prefer not to say, Gender not reported, Other gender, Other descriptors, Median age, Age reported as, Gender reported as, Study 0 rows, Study label, Study type, Reused from, Count basis, Gender term.

Fetching cost:
- **Metadata:** ~40–50 API calls to discover and list the VR 2015–2019 volumes (5 conference proceedings, 5 TVCG issues).
- **Full text:** ~325 calls, within one day's cap (invited papers dropped, so no title searches needed).

### Open questions *(compiled 2026-10-13; answers from the user 2026-10-13 and 2026-10-15 in italics)*

**A. Previous dataset (2015–2019)**
1. What does each missing-value code mean: `-`, `?` and `NA`? *All mean NA. The new extraction uses only NA.*
2. Should the 31 "invited" papers be kept or dropped? The 2020+ scope excludes this kind of paper. *Dropped.*
3. Should the re-extracted 2015–2019 data become part of the follow-up's dataset, or only serve as a test set? *Include it (2026-10-15). Goal and §1 updated: the 2015–2019 rows cover IEEE VR only.*
4. What conventions did the old coding use? *Answered:*
   - recruited or analyzed counts: *unknown, but probably recruited. Analyzed is preferred; the new extraction adds a Count basis column (recruited / analyzed / unknown).*
   - what counted as a separate study: *new participants.*
   - whether pilot studies were counted: *no.*
   - whether `males`/`females` covered only binary categories: *yes. The only other category reported in the whole dataset was non-binary.*
   - why papers with no study have total `0`: *treat it as NA.*
5. Should the 6 rows where males + females ≠ total be investigated now, or left for the comparison to sort out? *Left for the comparison.*
6. Was the old dataset complete for VR 2015–2019? This can be checked against Xplore's paper counts (2017 conference, with 23 papers, looks low). *To check. This happens naturally when the VR 2015–2019 metadata is fetched.* Checked 2026-10-13 against `data/index_2015-2019.csv` (fetched with `config/volumes_2015-2019.json`): all 325 old non-invited papers were found on Xplore. Journal counts match exactly every year. The conference volumes hold more because they include short papers (2015) and workshop papers (2019, pages ~1400+), which the old coding left out. That's consistent with a full-papers-only scope, not missing data. Six conference papers weren't in the old data; a collaborator checked them on 2026-10-13. Only one was a real omission: 2019 article 8798247, "Immersive Spatial Audio Reproduction…", which is **added** (326 papers). The three 2015 papers (7223465–7223467) are workshop papers, and the two 2018 ones (8446227, 8446583) are 2-page posters with bad page data on Xplore. All five stay out. Two 2019 records added to the volume later (9044162, 9044164) are probably workshop papers. One more 2018 record passes the automatic filters: 8446264, "The 2018 VGTC Virtual Reality Career Award" (front matter; Xplore `access_type` EPHEMERA, but it has an author and a normal page range). It also stays out. So `index_2015-2019.csv` (404 records) is only an intermediate step, and `index_2015-2019_test.csv` (326) is the 2015–2019 paper list. 8798247 has no old coding to compare against. It has no formal study, only "verbal feedback on four test scenes from two experienced and two untrained subjects", which raises the edge case below.
7. Should the old `category` field (14 topics) be kept for comparing topics across the two periods, and the 2020+ papers mapped onto it? Or drop topics and use keywords only? *Keywords only, collected for the new analysis.*
8. How many papers for tuning and how many held out for testing? Suggested: ~30–40 tuning papers (oversampling multi-study ones) and ~300 held out. *To discuss further.*

**B. Counting rules** (these change the numbers)

9. Recruited or analyzed participants? *Analyzed, with exclusions in notes, plus the Count basis column.*
10. How should pilot, expert-only and crowdsourced studies be handled? *Add a Study type column.* (Pilots are recorded but, as in the old coding, not counted as studies in the analysis.)
11. Gender vs. sex wording? *A column recording the paper's own term (gender / sex / unclear).*
12. Should there be a paper-level participant total, and if so, how are studies with overlapping participants handled? *Yes: a Study 0 row holding the total number of unique participants the paper reports.*
13. When demographics are reported only for all studies combined, should they be copied onto each study's row (the current draft rule), or left as **NA** with a flag? *NA with a flag.*
14. What counts as a separate study? For example, one participant group doing two experiments, or a study a paper reuses from earlier work. *A separate study has new participants. One group doing "two experiments" is one experiment with two blocks.*
    - *Reused studies (2026-10-15): participants already counted in this dataset must not be counted twice; participants not counted before are included.* Rule added to §3 (Reused from column). Finding the source paper: the full-text XML has in-text citation numbers (`<xref ref-type="bibr" rid="ref11">`) but **no reference list**, so a citation can't be resolved to a paper from the XML alone. Proposed: (1) extraction marks any study the paper says it reuses, with the quote; (2) a script lists candidate source papers in the index, i.e. earlier papers sharing an author, with title similarity; (3) a person confirms the source from the paper's reference list on Xplore. Reuse should be rare, so step 3 is a small manual job. A further automatic check catches unflagged reuse: two papers in the index that share an author and report identical N and demographics are flagged for review.
    - *Informal feedback counts as a user study, Study type `Informal` (2026-10-15).* So 8798247 is `Has user study: Yes`, Study type `Informal`, N = 4.

**Follow-ups raised by these answers** *(all confirmed 2026-10-15)*:
- **Combined demographics go on Study 0.** When a paper reports demographics only for all studies combined, they go on the Study 0 row, and the per-study rows get NA with a flag. This follows from 12 and 13.
- **Pilots and Study 0.** Study 0 excludes pilot participants, to match the old coding. Otherwise a paper's total would mix counted and uncounted studies.
- **Single-study papers get a Study 0 row too**, duplicating Study 1, so every paper with a study has a total on the same row number.
- **When Count basis is "unknown".** Many papers give one N and never mention exclusions. Proposed: record that as unknown rather than assuming analyzed, so the column measures how often papers make this clear.

**C. Schema**

15. The rules above imply columns the schema doesn't have yet: study kind, gender/sex term, notes and a review flag. Should they be added? *Yes, as needed; added to §3 below, along with Count basis.*
16. Keywords: author terms, IEEE terms, or both? Both are already in the cached metadata (`author_terms`, `ieee_terms`). *Both, as two columns.*
17. Should Article number stay as the paper identifier? DOI is the alternative. *Both, as two columns.*
18. How should Other participants be split? It currently adds non-binary, undisclosed and prefer-not-to-say together. Should those be counted separately? *A separate column for each, plus a catch-all for anything that doesn't match.* Added to §3 as Non-binary, Prefer not to say, Gender not reported and Other gender, with Other descriptors keeping the catch-all's labels verbatim. The old dataset has only non-binary, so only that column can be compared.
19. Should age values stay exactly as reported, or be converted to a single format (e.g., a median reported where a mean is expected, or only a range)? *To discuss further.* The user asked how a median or a range could become a mean. It can't, exactly; it can only be estimated. Meta-analyses use published formulas for this: Hozo et al. (2005) and Wan et al. (2014) estimate mean and SD from the median plus range or interquartile range, assuming a roughly symmetric distribution. Ages of convenience samples are usually right-skewed (many students, a few older participants), so these estimates run low. Proposed: extraction stores exactly what's reported, with a Median age column so a median never lands in Mean age. Any estimate is made later in the analysis, labelled as estimated, with a sensitivity check that leaves those papers out. *Decided 2026-10-15 (answer to 38 governs): record age in the existing columns (Min, Max, Mean, Median, SD), plus an Age reported as column saying which forms the paper gave. Converting between forms is left to the analysis.*

**D. Extraction pipeline**

20. Should extraction run as a script calling the Claude API (recommended) or through subagents? Running it through the API needs an API key in `.env`.
21. Which model(s), and what budget? Current pricing still needs checking.
22. Should the abstract be passed to the model too? The XML has no abstract, but the cached metadata does, and abstracts often state N.
23. Should the step-by-step plan above (steps 1–2) be rewritten to work from `data/fulltext/*.xml`? It still describes converting PDFs with PyMuPDF.
24. Should the keyword search that narrows each paper to its participant passages stay, or should the model read the whole paper?

**E. Validation**

25. Adopt the proposed validation design in place of the 10% second-reader check?
26. What second model family or second prompt for the agreement check?
27. What stopping-rule thresholds? Suggested: minimum 30 checks, stop when the 95% interval is within ±5 points, maximum 100.
28. Which fields count as key for the per-field audit?
29. Should part of the test set be reviewed blind, without the model's answer visible? If so, how many papers?
30. Will a second human code ~20 papers so human–human agreement can be reported?
31. How big should the 2020+ audit be? It's needed for the new gender columns and for differences in reporting since 2019.

**F. Scope and housekeeping**

32. When ISMAR 2026 appears on Xplore, should it be added (rerun discovery)? Or freeze the dataset at a cutoff date? *Add it when available (2026-10-15).* The risk is timing: the conference proceedings can take weeks to months after the conference to appear on Xplore, while the TVCG special issue usually appears around the conference. Still to decide: a last date to wait until, after which ISMAR 2026 is left out (or only its journal track kept) and the methods say so.
33. Should the untracked dotfiles in the repo root (`.bashrc`, `.profile`, `.claude/` etc.) be deleted or gitignored?
34. Should the full-text API's coverage of 2015-era papers be confirmed with a small test fetch before committing to the plan?
35. `data/` is gitignored, so `data/IEEEVR2015-2019.xlsx` isn't in git or in the 2026-10-09 backup. Should it be backed up separately?

**G. Data capture and format** *(raised 2026-10-14; answered 2026-10-15)*

36. Counts computed from percentages that aren't whole numbers (e.g., 37.5% of 22 = 8.25)? *Round to the nearest whole number, and record whether the paper gave counts or percentages* (Gender reported as column, §3).
37. Gender counts that don't add up to Total participants? *Record the numbers as given and set Review flag.*
38. Ages in other forms ("over 18", "18–25" brackets, age groups with counts)? *Keep the Min, Max, Mean, Median and SD columns, and add Age reported as. Analyze further after extraction.* This answer governs where it differs from the answer to 19. Rule added to §3: every form goes into the five columns (e.g., "over 18" → Min age 18; brackets → Min/Max from the lowest and highest bracket ends), and Age reported as holds the paper's age text verbatim, so the analysis can separate the forms. *(2026-10-15: verbatim text rather than a list of form categories.)*
39. Where do First/Last author and keywords come from? *User's guess: the paper is more accurate than the metadata.* **Proposed: metadata.** The full-text XML holds only the article body, with no title block or author list, so the paper's own author list is available only from PDFs, which we have for 109 of 1,980 papers. Xplore's author list is built from the publisher's final files, so author order normally matches the paper. Differences are mostly formatting (accents, initials). Accuracy is checked in the audit (First author and Total authors against the old data for 2015–2019). Keywords exist only in the metadata. *To confirm.*
40. Delivered file format? *One CSV with all the data. Keywords as given, `;`-separated. Mean values exactly as reported, keeping decimals.* Proposed details: UTF-8, numbers written as text exactly as printed (so 24.30 stays 24.30). Checked 2026-10-15: 32 of the 188,872 cached keyword strings, on about ten papers, contain a `;` themselves, all garbled ACM classification strings. They're kept as given.
41. A written old-to-new column mapping? *Yes, though it matters little: the old data has only one participant who was neither male nor female.* Added under "Previous dataset" above.

Questions 1–7, 9–19, 32 and 36–41 are answered (39 needs confirming). Still open: 8 (tuning/test split), 20–31, 33–35, and the ISMAR 2026 wait date in 32.

## 3. Data Schema

Delivered as **one UTF-8 CSV** holding every venue and year. One row per study, so a paper with several studies has several rows, plus a **Study 0** row per paper holding the paper-level total of unique participants and the combined demographics. Study 0 leaves out pilots and reused studies already counted elsewhere in the dataset. A single-study paper gets a Study 0 row too, a copy of Study 1. The paper-level fields (Article number through Total authors) repeat on each of its rows. A paper with no user study gets a single row, with `Has user study: No` and Study number **NA**. Article number plus Study number identifies a row.

| Field | Notes |
|---|---|
| Article number | IEEE Xplore article number (`article_number` in `data/index.csv`); identifies the paper and links rows from the same paper |
| DOI | From the cached metadata |
| Year | Publication year (conference presentation year for journal-track papers, to keep it aligned with the venue-year the paper "belongs to") |
| Venue | `IEEE VR` or `ISMAR` — which conference the paper belongs to, regardless of track |
| Type | `Conference` or `Journal` |
| Title | Full paper title |
| First author | From the cached metadata (proposed; see Q39) |
| Last author | From the cached metadata (senior/PI author by convention, if distinguishable from "second author" in a 2-author paper) |
| Total authors | Integer count |
| Author keywords | `author_terms` from the cached metadata, semicolon-separated, each term as given |
| IEEE terms | `ieee_terms` from the cached metadata, semicolon-separated, each term as given |
| Has user study | `Yes` / `No` — whether the paper involved human participants |
| Study number | 0 for the paper-level total row; 1, 2, … in the order the paper presents its studies; **NA** for a paper with no user study |
| Study label | The paper's own name for the study, copied verbatim (e.g., "Study 2", "Experiment 1", "Pilot study"); **NA** if the paper doesn't name it, for Study 0, or if there is no user study |
| Study type | e.g., `Main`, `Pilot`, `Expert`, `Crowdsourced`, `Informal` (informal feedback sessions; the list isn't fixed and may grow in the pilot); **NA** for Study 0 or no study |
| Reused from | For a study the paper reuses from earlier work: the source paper's Article number if it's in this dataset, otherwise the citation as the paper gives it. **NA** for a new study, Study 0, or no study |
| Total participants | Integer, for this study (unique participants for the whole paper on Study 0); **NA** if no study or count not reported |
| Count basis | `Recruited`, `Analyzed` or `Unknown`: which count Total participants holds. `Unknown` when the paper gives one N without saying which |
| Female participants | As reported by authors' own terminology; **NA** if not reported |
| Male participants | As reported by authors' own terminology; **NA** if not reported |
| Non-binary participants | **NA** if not reported |
| Prefer not to say | Participants who declined to give gender/sex; **NA** if not reported |
| Gender not reported | Participants the paper says gave no answer or whose gender is unknown (as distinct from declining); **NA** if not reported |
| Other gender | Catch-all for any other category (e.g., "other," "genderqueer"); **NA** if not reported |
| Other descriptors | The authors' own labels for the Other gender count, copied verbatim; **NA** if none |
| Gender reported as | `Counts` or `Percentages` (counts were computed and rounded), or `Both`; **NA** if no gender/sex data reported |
| Min age | Lower end of the ages reported (range, lower bound, or lowest bracket); Age reported as shows which; **NA** if not reported |
| Max age | Upper end of the ages reported (range or highest bracket); Age reported as shows which; **NA** if not reported |
| Mean age | As reported, decimals kept exactly as printed; **NA** if not reported (never a median) |
| Median age | As reported; **NA** if not reported |
| Age SD | As reported, decimals kept exactly as printed; **NA** if not reported |
| Age reported as | The paper's age text for this study, copied verbatim (e.g., "aged 18–35 (M = 24.3, SD = 3.1)", "all participants were over 18"). If age appears in more than one place, the passages are joined with ` … `. **NA** if age not reported |
| Gender term | The paper's own wording: `gender`, `sex` or `unclear`; **NA** if no gender/sex data reported |
| Notes | Free text: exclusions, derivations (e.g., counts computed from percentages), anything unusual |
| Review flag | `Yes` when the row needs human review (e.g., demographics reported only for all studies combined, gender counts that don't add up to Total participants, failed automatic checks); otherwise `No` |

Any field the paper does not report gets the literal string **NA** — never a blank cell and never `0` (a blank/0 is ambiguous between "not reported" and "reported as zero"). This applies to every field above except Article number, Year, Venue, Type, Title, First/Last author, and Total authors, which always come from the metadata. The participant and age fields describe the row's own study, not the whole paper.

### Extraction rules / edge cases
- **Use authors' own terminology** for gender categories rather than normalizing; keep a separate "descriptors" field to preserve nuance (some papers use "sex," some "gender," some conflate the two — note this ambiguity in a comments column if needed).
- **Missing data stays missing** — do not infer or estimate; mark it **NA** rather than guessing. If a paper reports total N and % female but not raw counts, compute raw counts, round to the nearest whole number, set Gender reported as to `Percentages` and note the derivation; if age is reported only as a range (no mean/SD) or only as mean (no range), fill in only what's given and mark the rest **NA**.
- **Gender counts that don't add up**: if female + male + the other gender columns ≠ Total participants, record the numbers as given and set Review flag.
- **Age in other forms**: fill the Min, Max, Mean, Median and SD columns from whatever the paper gives, and copy the paper's age text into Age reported as so the analysis can tell the forms apart. "Aged 19–34" → Min 19, Max 34. "Over 18" → Min 18, Max **NA**. Age groups ("12 aged 18–25, 8 aged 26–35") → Min 18, Max 35.
- **Informal feedback** (e.g., a few people trying the system and commenting) counts as a user study: `Has user study: Yes`, Study type `Informal`, with whatever N the paper gives.
- **Reused studies**: when a paper reports a study from earlier work, record it as a study row with Reused from set. If the source paper is in this dataset, those participants are already counted there, so the row is left out of Study 0 and of the analysis. Otherwise (the source is outside the dataset), it's counted normally. Set Review flag until the source is confirmed (see Q14).
- **Multiple studies in one paper**: one row per study, numbered in the order the paper presents them, with the paper's own name for each study in Study label (so an unnumbered pilot before "Study 1" is Study number 1, Study label "Pilot study", Study type `Pilot`). A separate study has **new participants**: one group doing "two experiments" is one study with two blocks, even if the paper calls them Experiment 1 and 2. Study 0 holds the paper's total of unique participants, leaving out pilots and reused studies already counted; don't add studies together to get it unless the paper says the participants were different people. A single-study paper's Study 0 copies Study 1 (unless that study is a pilot). If demographics are reported only for all studies combined, put them on Study 0, leave the study rows' demographics **NA** and flag them for review.
- **Recruited vs. analyzed**: record the analyzed count when the paper gives it, note exclusions in Notes, and set Count basis to say which count the row holds.
- **Within-subjects/between-subjects or multiple conditions**: participant count = unique individuals, not condition-participation instances.
- **No demographics reported at all** but a study clearly involved human participants: still mark `Has user study: Yes`, fill total N if available, mark gender/age fields **NA** rather than `0`.

## 4. Tooling

All scripts are Python (run so far with 3.12.3; `pyproject.toml` requires ≥3.12) using the standard library plus `requests`, with dependencies managed by uv in `pyproject.toml` and `uv.lock`. They live in `scripts/`. Run them with `uv run scripts/<name>.py`.

| Script / file | Status | Purpose |
|---|---|---|
| `scripts/xplore.py` | Done | Shared API client. Reads the key from `.env`, caches every successful response in `data/raw/api/` (keyed by the query parameters, so a query is never paid for twice), logs call times in `data/api_calls.json`, stops at 200 calls per rolling 24 hours, and spaces calls ≥0.5 s apart. Also usable as a one-off probe: `uv run scripts/xplore.py publication_number=9583730`. |
| `scripts/discover_volumes.py` | Done | Step 1a: lists candidate volumes per venue/year with hit counts. Only needed again when new volumes appear (e.g. ISMAR 2026). |
| `config/volumes.json` | Done | The reviewed list of 26 in-scope volumes and their Xplore filters (gitignored; the volumes are summarized in §2). |
| `scripts/fetch_metadata.py` | Done | Step 1b: pages through each volume, filters out front matter, writes `data/index.csv` (papers) and `data/index_all.csv` (all records with status/reason). Rerunning is free once responses are cached. |
| `scripts/download_pdfs.py` | Done; blocked on network for subscription papers | Step 3 (see above): throttled, resumable PDF download. `--open-access-only` limits it to papers that need no subscription; `--limit N` caps a run (default 300). |
| `scripts/fetch_fulltext.py` | Written 2026-10-02; replaces PDFs as the full-text route | Full-text XML via the IEEE Full-Text API, using the access token `IEEE_XPLORE_FT_ACCESS_TOKEN` in `.env`. It needs no entitled network. It POSTs `/auth/token` (form body, as in IEEE's Python SDK) to get a 15-minute `cltoken` (refreshed every 10 min or on "Token Expired"), then GETs `/search/document/<n>/fulltext?format=xml`, which returns the article `<body>` (sections, tables, captions; no abstract or references). Saves `data/fulltext/<n>.xml`, skips papers already fetched, shares the 200/day call budget with `xplore.py`, backs off and retries (1, 2, 4, 8 min) on "Over Qps" and 5xx errors, and logs to `data/logs/fulltext.csv` and `fulltext_run.log`. `--limit N` caps a run. Open-access papers go first. `--index` picks a different paper list (e.g., the 2015–2019 test set). |
| `scripts/match_previous.py` | Done 2026-10-13 | Matches the previous paper's hand-coded VR 2015–2019 papers (`data/IEEEVR2015-2019.xlsx`, invited papers dropped) to the Xplore records from `fetch_metadata.py --volumes config/volumes_2015-2019.json --out index_2015-2019`, matching titles fuzzily and one-to-one, and adds the confirmed omission 8798247. Writes `data/index_2015-2019_test.csv` (326 papers, with old title, old type and match score). This, not `index_2015-2019.csv`, is the 2015–2019 paper list (see Q6). Full text for all 326 was fetched by 2026-10-14. |

`data/` (API cache, call log, index, PDFs) is gitignored: it's reproducible from the scripts, and the PDFs are copyrighted.

Later stages:
- PDF text extraction (e.g., `pdftotext`, or a PDF-parsing library) to pull candidate "Participants" sections automatically as a first pass, followed by manual/LLM-assisted verification given how inconsistently this information is reported.
- Store the working dataset as CSV/spreadsheet (one row per study; see §3) for downstream analysis (e.g., trends over time in gender balance, reporting completeness).

## 5. Known Limitations

- Coverage is uneven: IEEE VR runs 2015–present, ISMAR only 2020–present, so venue comparisons are limited to 2020 onward. Full text for all papers came from the IEEE Full-Text API (see §4).
- Demographic reporting norms still vary within 2020–present (non-binary/other categories are more common than in earlier years but still inconsistently reported), so absence of an "other" count doesn't necessarily mean an all-binary participant pool.
- Determining "last author" as the senior/PI author is a convention, not a guarantee — some subfields/labs order authors alphabetically or by contribution instead.

# ChiEAC Supply Bank Allocator — Acceptance & Evidence Matrix

**Working review — November 6, 2026 | Gate 7 / Section 13 of Benjamin's Project Brief**
**Repository baseline:** `e740b0fdc1d48d9705cd62b42c602d85fe45dd63` (before proposed CP7.3A correction).
**Status convention:** **PASS** = evidence covers the stated check; **PARTIAL** = code/limited evidence exists but full acceptance is unverified or a benchmark remains unmet; **PENDING** = no adequate completion evidence. **Not a final Gate 7 sign-off.**

## Section 13 — Definition of done

| Area | Brief requirement | Current evidence | Status / closure needed |
|---|---|---|---|
| Uploads | Four templates, mapping, planted-error validation, drop explanations, Demo Mode | Existing templates, cleaning/tests, uploaded screenshots showing corrections and derived tables | **PARTIAL** — retain original planted-error coverage evidence and verify the full upload path on final cloud release |
| Forecast | 4–8 weeks, method and backtest WAPE per site/size, survey cold-start labels, CSV/XLSX | Demo screenshots: 8-week run across 25 synthetic sites; provisional ranges and flagged/`N/A` series are disclosed | **PARTIAL** — some product-size WAPE values are N/A (not a scored accuracy result); confirm export formats and acceptable limitations with Benjamin |
| Allocation | Solver <10s at 80 sites; feasible supply/floor, equity controls, comparison, pick CSV | Reported synthetic 80×20 stress benchmark ~1.048s worker, tests for feasibility; screenshot shows weighted unmet improvement | **PARTIAL** — original brief asks worst-site fill to *rise*; recorded comparisons show preservation/equality, not demonstrable strict increase. Seek acceptance, do not alter data to force it |
| Alerts | WOS by size, short/long flags, mismatch chart, suggested actions | Screenshots and source show both on-hand/projected-cycle WOS and 8-week gap logic | **PARTIAL** — WOS thresholds and full-cycle shortages differ by design; recheck planted inventory/alerts on final cloud build |
| Scenarios | Donation, pending, new partner, size shift, purchase budget; baseline deltas | Source/tests; verified local -20% *Community Donations only* screenshot, ~0.94s; historic synthetic purchasing benchmarks | **PARTIAL** — final cloud and non-donation scenario checks remain; no real procurement or field benefit claim |
| Report | One-page PDF for tiny and full demo; branding from config; click-to-export | PDF screenshot; synthetic A/B/C eight-week test; CP7.1 provenance labeling: 474 local tests, 3 smoke checks | **PARTIAL** — config-based branding not established (bank name/logo entered in UI); verify CP7.1 source labels on hosted app and resolve branding requirement with Benjamin |
| Deployment | Public URL; no exposed traces; phone/laptop; privacy statement | Public Streamlit link, uploaded desktop screenshots, earlier user-reported mobile/load smoke | **PARTIAL** — verify newest hosted commit and a new demo→PDF cloud run; sub-10s true cold load not instrumented; no exhaustive public security review |
| Documentation | README local run <10min; dictionary, methods, screenshot user guide, onboarding, decisions, synthetic spec | `e740b0f` includes new guides and 10 images; README/methods reconciled; Word/PDF versions available separately | **PARTIAL** — clean Python 3.13 install under 10min unverified; maintain Word/PDF handoff version and confirm reader usability |
| Quality | pytest pass; pinned dependencies; `v1.0` tag | User-run November 6: **474 passed, 0 failed, 17 existing PuLP warnings** on CP7.1; requirements pinned | **PARTIAL** — rerun full pytest after CP7.3A fix; release tag not yet created |
| Narrative | Kickoff + five progress posts + launch post tagging both accounts; 4–6 min demo; practitioner quote or documented attempt | Three practitioner feedback invitations independently confirmed sent November 2 | **PENDING** — verify existing posts, record 4–6 min video and launch post, and obtain quote permission or document no response |
| Handoff | Final email: live URL, repo, video, docs, config example, issues/future ideas | Working project state, decisions, guides, live app and source repo | **PENDING** — config example/waiver, organizational ownership and final email to Benjamin need closure |

## Gate 7 special benchmarks and sign-off

| Gate 7 benchmark | Status | Evidence / required next action |
|---|---|---|
| Section 13 acceptance checklist fully checked | **PARTIAL** | Use the matrix above; preserve unmet criteria as OPEN until they have evidence or explicit sign-off |
| Practitioner quote (with permission) or documented attempts | **PARTIAL** | Three dated outreach emails sent Nov 2; no practitioner replies established in checked mailbox; log attempts and date of follow-up without fabricating a quote |
| README enables local run in <10 minutes | **PENDING** | Fresh machine/clean virtual environment using Python 3.13; record start/end, install/run results and environment. A normal existing `.venv` run is not this benchmark |
| Live final demo to Benjamin | **PENDING** | Record date, what was demonstrated and feedback; do not claim attendance/approval in advance |
| 4–6 minute recorded demonstration | **PENDING** | Capture synthetic-only workflow and check link is accessible |
| Launch post with live URL and demo video; both tags | **PENDING** | Draft, obtain review, publish then record actual post URL (do not claim published before evidence) |

## Risk register and release decisions

1. **Display precision messaging (CP7.3A):** A very small positive raw worst-site fill-rate delta can currently display as `+0.00 percentage points` while the page reports "increased." Proposed patch classifies the *displayed* two-decimal delta as unchanged while retaining all underlying solver metrics. Requires targeted, full-suite and live smoke results; until then **FIX IN PROGRESS**.
2. **Strict worst-site benchmark:** Gate 4 original requirement requests an increase. A preserved/equal worst-site fill with improved equity-weighted unmet is analytically defensible, but is **not literal fulfillment**. Ask Benjamin to accept the documented trade-off or identify a permitted alternative. No synthetic manipulation.
3. **Branding from config:** Existing report supports optional bank name and logo inputs; source does not yet show a general YAML/JSON config-based app branding mechanism required in Brief Section 13. Decide on a small nonprofit-only config example or documented waiver, without commercialization.
4. **Privacy/ownership:** Public hosting receives uploaded files on a third-party server; avoid client-level sensitive data. Set an organizational owner for code/deploy/credentials and a maintenance contact before handoff.
5. **Scope:** The software and guide are a free nonprofit contribution; do not build commercial licensing, paid onboarding or client-specific paid deployments. These project constraints are **not** a legal judgment about OPT.

## Suggested final acceptance evidence packet

- `python -m pytest -q` log (after last source patch), CP7.3A local screenshot showing a neutral 0.00 pp delta, and public Streamlit smoke report.
- Full one-page synthetic PDF, and an eight-week tiny A/B/C PDF test result distinguished from real 3-site live uploads.
- Fresh setup report (<10min measured), mobile/laptop notes, documentation links, 4–6min video, outreach sent evidence, and actual LinkedIn links.
- Benjamin's acknowledgement of unresolved benchmark/config/hosting choices; final handoff email and approved `v1.0` tag only when release acceptance is complete.

**Evidence caution:** Older synthetic benchmark numbers (e.g., 3.18% weighted improvement at ~98.27% worst fill) and later screenshots (1.67% at ~83.7%) are from different settings/runs. Do not combine them into one result or claim verified community impact.

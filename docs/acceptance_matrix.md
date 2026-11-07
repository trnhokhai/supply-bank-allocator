# ChiEAC Supply Bank Allocator — Acceptance & Evidence Matrix

**Evidence reconciliation — November 6, 2026 | Gate 7 / Section 13 of Benjamin's Project Brief | CP7.4B addendum below**
**Repository baseline:** `de7223dd0cd87df72b103f29613dac9b9145d691` (CP7.4B nonprofit report branding; earlier checkpoint entries are historical).
**Status convention:** **PASS** = evidence covers the stated check; **PARTIAL** = code/limited evidence exists but full acceptance is unverified or a benchmark remains unmet; **PENDING** = no adequate completion evidence. **Not a final Gate 7 sign-off.**

## Section 13 — Definition of done

| Area | Brief requirement | Current evidence | Status / closure needed |
|---|---|---|---|
| Uploads | Four templates, mapping, planted-error validation, drop explanations, Demo Mode | Existing templates, cleaning/tests, uploaded screenshots showing corrections and derived tables | **PARTIAL** — retain original planted-error coverage evidence and verify the full upload path on final cloud release |
| Forecast | 4–8 weeks, method and backtest WAPE per site/size, survey cold-start labels, CSV/XLSX | Demo screenshots: 8-week run across 25 synthetic sites; provisional ranges and flagged/`N/A` series are disclosed | **PARTIAL** — some product-size WAPE values are N/A (not a scored accuracy result); confirm export formats and acceptable limitations with Benjamin |
| Allocation | Solver <10s at 80 sites; feasible supply/floor, equity controls, comparison, pick CSV | Reported synthetic 80×20 stress benchmark ~1.048s worker, tests for feasibility; screenshot shows weighted unmet improvement | **PARTIAL** — original brief asks worst-site fill to *rise*; recorded comparisons show preservation/equality, not demonstrable strict increase. Seek acceptance, do not alter data to force it |
| Alerts | WOS by size, short/long flags, mismatch chart, suggested actions | Screenshots and source show both on-hand/projected-cycle WOS and 8-week gap logic | **PARTIAL** — WOS thresholds and full-cycle shortages differ by design; recheck planted inventory/alerts on final cloud build |
| Scenarios | Donation, pending, new partner, size shift, purchase budget; baseline deltas | Source/tests; verified local -20% *Community Donations only* screenshot, ~0.94s; historic synthetic purchasing benchmarks | **PARTIAL** — final cloud and non-donation scenario checks remain; no real procurement or field benefit claim |
| Report | One-page PDF for tiny and full demo; branding from config; click-to-export | CP7.1 source labels and 8-week synthetic PDF verified previously on Cloud; CP7.4B nonprofit-only JSON default name/logo plus staff overrides implemented at `de7223d`; user supplied local one-page PDF screenshot with fictitious name and unchanged 55,486 modeled shortfall | **PARTIAL** — local branding/PDF visual and tests PASS; post-`de7223d` public-cloud branded PDF still pending; no genuine bank data validation or universal Unicode-font support claim |
| Deployment | Public URL; no exposed traces; phone/laptop; privacy statement | User-provided public-app screenshots show 8-week Forecast → Allocate → synthetic PDF working after `b8bbd5d`; earlier user-reported mobile check | **PARTIAL** — current synthetic public workflow visually passed, not independently browser-driven; server-cold under-10-second load and comprehensive hosting/security review are not established |
| Documentation | README local run <10min; dictionary, methods, screenshot user guide, onboarding, decisions, synthetic spec | Guides and ten synthetic screenshots committed (`e740b0f`); user-run clean Python 3.13 Windows probe completed clone, fresh env, uncached pip installation, imports and Streamlit health in **5.39 minutes** | **PARTIAL** — measured one-machine setup target met; Word/PDF usability and final artifact/organizational handoff review not yet signed off. Localhost health is not full operational acceptance |
| Quality | pytest pass; pinned dependencies; `v1.0` tag | User-run CP7.4B Windows regression **508 passed, 0 failed, 17 pre-existing PuLP deprecation warnings**; **35 targeted tests passed**. Display-precision fix remains regression-covered; requirements pinned | **PARTIAL** — code-quality tests met locally, but live final smoke, release tag and signoff pending. Do not represent old PuLP reference warnings as new failures |
| Narrative | Kickoff + five progress posts + launch post tagging both accounts; 4–6 min demo; practitioner quote or documented attempt | Three practitioner feedback invitations independently confirmed sent November 2 | **PENDING** — verify existing posts, record 4–6 min video and launch post, and obtain quote permission or document no response |
| Handoff | Final email: live URL, repo, video, docs, config example, issues/future ideas | Source repo, Markdown guides and `config/report_branding.json` example exist; continuity docs in progress, separate shareable Word/PDF guides previously generated | **PENDING** — verify current Word/PDF editions, video URL, nonprofit steward, public-cloud post-CP7.4B demo and final email; no handoff/ownership confirmation claimed |

## Gate 7 special benchmarks and sign-off

| Gate 7 benchmark | Status | Evidence / required next action |
|---|---|---|
| Section 13 acceptance checklist fully checked | **PARTIAL** | Nonprofit config branding now implemented and locally tested; local full suite 508 PASS. Strict worst-site rise, post-CP7.4B Cloud smoke, narrative, organizational ownership and formal signoff remain open |
| Practitioner quote (with permission) or documented attempts | **PARTIAL** | Three dated outreach emails sent Nov 2; no practitioner replies established in checked mailbox; log attempts and date of follow-up without fabricating a quote |
| README enables local run in <10 minutes | **PASS on tested Windows machine** | User-run fresh install probe: **5.39 minutes** from Git clone through new Python 3.13 venv, uncached dependency install, imports and temporary Streamlit localhost health. Does not guarantee every machine or full user workflow. JSON/logs held in separate local probe folder |
| Live final demo to Benjamin | **PENDING** | Record date, what was demonstrated and feedback; do not claim attendance/approval in advance |
| 4–6 minute recorded demonstration | **PENDING** | Prepare synthetic-only recording and accessible URL; not yet recorded or published |
| Launch post with live URL and demo video; both tags | **PENDING** | Draft, obtain review, publish then record actual post URL (do not claim published before evidence) |

## Risk register and release decisions

1. **Display precision messaging (CP7.3A):** FIX VERIFIED LOCALLY AND VISUALLY ON PUBLIC APP. The UI now reports a neutral **0.00 percentage-point** difference when both worst-site fill figures display 83.7%, avoiding an unsupported claim of strict improvement. Underlying optimizer output remains unchanged. User-run **488 passed, 17 existing warnings**; hosted synthetic screenshot shows the corrected caption. No independent browser automation was performed.
2. **Strict worst-site benchmark:** Gate 4 original requirement requests an increase. A preserved/equal worst-site fill with improved equity-weighted unmet is analytically defensible, but is **not literal fulfillment**. Ask Benjamin to accept the documented trade-off or identify a permitted alternative. No synthetic manipulation.
3. **Branding from config:** CP7.4B **implemented** optional read-only nonprofit config `config/report_branding.json` and a bounded logo path. User-run 35 targeted / 508 full tests passed; local one-page PDF shows fictitious brand override. Cloud verification after `de7223d` and formal Brief acceptance have **not** been independently established. No commercial/tenant implementation.
4. **Privacy/ownership:** Public hosting receives uploaded files on a third-party server; avoid client-level sensitive data. Set an organizational owner for code/deploy/credentials and a maintenance contact before handoff.
5. **Scope:** The software and guide are a free nonprofit contribution; do not build commercial licensing, paid onboarding or client-specific paid deployments. These project constraints are **not** a legal judgment about OPT.

## Suggested final acceptance evidence packet

- User-run post-CP7.4B `python -m pytest -q`: **508 passed, 0 failed, 17 known PuLP reference warnings**; 35 targeted tests passed. Local branded synthetic one-page PDF screenshot has a fictitious bank name. Prior cloud PDF/precision screens predate `de7223d`; preserve evidence separately and rerun public Cloud workflow for new branding.
- Full one-page synthetic PDF, and an eight-week tiny A/B/C PDF test result distinguished from real 3-site live uploads.
- Fresh setup report: **5.39 min** on Windows / Python 3.13 (clone, clean uncached install, imports, local Streamlit health), with separate local result JSON and logs; mobile/laptop notes, docs links, outreach sent evidence. Video and actual LinkedIn links still pending.
- Benjamin's acknowledgement of unresolved benchmark/config/hosting choices; final handoff email and approved `v1.0` tag only when release acceptance is complete.

**Evidence caution:** Older synthetic benchmark numbers (e.g., 3.18% weighted improvement at ~98.27% worst fill) and later screenshots (1.67% at ~83.7%) are from different settings/runs. Do not combine them into one result or claim verified community impact.

## CP7.3B.3 — Explicit evidence boundaries and closure sequence (November 6, 2026)

**Verified against the user's supplied artifacts, not independently rerun by this documentation change:** 488 local test passes with 17 existing PuLP warnings; hosted synthetic 8-week Forecast → Allocate → one-page PDF, with 331,802 allocated units and 55,486 modeled planning unmet; corrected neutral worst-site display; 5.39-minute fresh Windows/Python 3.13 setup and local Streamlit health. The PDF marks synthetic source, not real-world impact. A complete independent security/privacy audit, genuine cold server wake test, all hosted scenarios and an external practitioner pilot have not been established.

**Release blockers requiring decision or deliverable:**

1. **Benjamin decision:** the observed constrained benchmark improves equity-weighted unmet but protects rather than strictly *increases* worst-partner fill. Request a documented acceptance of this limitation or a specific approved alternative; do not tune fabricated inputs to force a win.
2. **Benjamin decision:** whether current bank name/logo inputs satisfy the branding requirement, or a small free nonprofit configuration example is required. Do not implement a larger deployment or commercial customization system.
3. **Organizational stewardship:** confirm ChiEAC code/deploy maintenance owner, account access and preference to retain free Community Cloud unless there is an actual operational need to migrate. No personal payment needed.
4. **User deliverables:** record and verify a 4–6-minute synthetic demo, review launch/post requirements with Benjamin, retain dated practitioner outreach evidence and permissions for any quotes, then send final handoff links.
5. **Release control:** update this matrix after decisions and evidence. Create `v1.0` only when the required signoff is given and remaining PARTIAL/PENDING items are explicitly resolved or accepted as limitations.

No claim of Gate 7 full PASS or field validation is made here.


## CP7.4B — Current evidence addendum (November 6, 2026)

**Code commit on `main`:** `de7223dd0cd87df72b103f29613dac9b9145d691` (source/config/tests only). Decision 048 in `docs/DECISIONS.md` keeps tested optimizer unchanged and records its **strict worst-site-rise** acceptance deviation. The old CP7.3B.3 paragraph above is a historical evidence checkpoint; its then-open branding implementation requirement was subsequently **implemented**, but not yet accepted or post-deploy verified.

**Nonprofit branding:** `config/report_branding.json` supplies neutral PDF default `Supply Bank` with no logo; an authorized PNG/JPEG inside `config/branding_assets/` can be configured. Staff may optionally override the name/logo in the Report form for that PDF; no config file is written by the UI. This is report identification for free nonprofit use, **not** commercial tenant customization, client acquisition or paid service.

**User-observed evidence:** Windows `pytest`: **508 passed, zero failed, 17 pre-existing warnings**; **35 targeted passed**. Local Report UI visibly loads `config/report_branding.json` with default `Supply Bank`. A local PDF screenshot shows one page with override `Community Test Supply Bank`, explicit **SYNTHETIC DEMONSTRATION**, 366,842 observed distribution units across 25 logged partners, 55,486 modeled shortfall and 55,486 SKU gap; dollar total correctly unavailable when unit prices are missing. This is user-supplied manual evidence, not independent Cloud QA or field use.

**Still open:** (1) post-`de7223d` hosted Demo Mode → 8-week Forecast/Allocate → brand-name PDF smoke, (2) 4–6-minute video and verified live link, (3) actual required LinkedIn post evidence, (4) Benjamin's explicit acceptance/waiver of unchanged worst-partner fill vs. original strict-rise wording, (5) organization stewardship/maintenance and final handoff, and (6) approved `v1.0` tag. Keep Gate 7 **PARTIAL** rather than declaring full PASS. A true server-cold load and external practitioner field pilot remain unverified.

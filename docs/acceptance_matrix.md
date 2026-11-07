# ChiEAC Supply Bank Allocator — Acceptance & Evidence Matrix

**Evidence reconciliation — November 6, 2026 | Gate 7 / Section 13 of Benjamin's Project Brief**
**Repository baseline:** `b8bbd5d3f062cb3b1caffba5e9a8158f6a7f11d9` (CP7.3A committed; CP7.3B evidence reviewed after).
**Status convention:** **PASS** = evidence covers the stated check; **PARTIAL** = code/limited evidence exists but full acceptance is unverified or a benchmark remains unmet; **PENDING** = no adequate completion evidence. **Not a final Gate 7 sign-off.**

## Section 13 — Definition of done

| Area | Brief requirement | Current evidence | Status / closure needed |
|---|---|---|---|
| Uploads | Four templates, mapping, planted-error validation, drop explanations, Demo Mode | Existing templates, cleaning/tests, uploaded screenshots showing corrections and derived tables | **PARTIAL** — retain original planted-error coverage evidence and verify the full upload path on final cloud release |
| Forecast | 4–8 weeks, method and backtest WAPE per site/size, survey cold-start labels, CSV/XLSX | Demo screenshots: 8-week run across 25 synthetic sites; provisional ranges and flagged/`N/A` series are disclosed | **PARTIAL** — some product-size WAPE values are N/A (not a scored accuracy result); confirm export formats and acceptable limitations with Benjamin |
| Allocation | Solver <10s at 80 sites; feasible supply/floor, equity controls, comparison, pick CSV | Reported synthetic 80×20 stress benchmark ~1.048s worker, tests for feasibility; screenshot shows weighted unmet improvement | **PARTIAL** — original brief asks worst-site fill to *rise*; recorded comparisons show preservation/equality, not demonstrable strict increase. Seek acceptance, do not alter data to force it |
| Alerts | WOS by size, short/long flags, mismatch chart, suggested actions | Screenshots and source show both on-hand/projected-cycle WOS and 8-week gap logic | **PARTIAL** — WOS thresholds and full-cycle shortages differ by design; recheck planted inventory/alerts on final cloud build |
| Scenarios | Donation, pending, new partner, size shift, purchase budget; baseline deltas | Source/tests; verified local -20% *Community Donations only* screenshot, ~0.94s; historic synthetic purchasing benchmarks | **PARTIAL** — final cloud and non-donation scenario checks remain; no real procurement or field benefit claim |
| Report | One-page PDF for tiny and full demo; branding from config; click-to-export | User-provided public-app synthetic PDF screenshot shows one readable page, automatic synthetic label and consistent 55,486-unit planning shortfall; CP7.1 local mixed/stale checks passed | **PARTIAL** — public synthetic provenance visually verified; uploaded/mixed cloud paths and config-based branding are not independently accepted. Obtain config example or Benjamin approval of current UI branding |
| Deployment | Public URL; no exposed traces; phone/laptop; privacy statement | User-provided public-app screenshots show 8-week Forecast → Allocate → synthetic PDF working after `b8bbd5d`; earlier user-reported mobile check | **PARTIAL** — current synthetic public workflow visually passed, not independently browser-driven; server-cold under-10-second load and comprehensive hosting/security review are not established |
| Documentation | README local run <10min; dictionary, methods, screenshot user guide, onboarding, decisions, synthetic spec | Guides and ten synthetic screenshots committed (`e740b0f`); user-run clean Python 3.13 Windows probe completed clone, fresh env, uncached pip installation, imports and Streamlit health in **5.39 minutes** | **PARTIAL** — measured one-machine setup target met; Word/PDF usability and final artifact/organizational handoff review not yet signed off. Localhost health is not full operational acceptance |
| Quality | pytest pass; pinned dependencies; `v1.0` tag | User-run November 6: **488 passed, zero failures, 17 previously existing PuLP deprecation warnings**, repeated; CP7.3A fill-rate wording UI locally and on public app visually checked; pinned dependencies | **PARTIAL** — regression criterion demonstrated locally; `v1.0` tag and final signoff still pending. Warnings are compatibility notices, not proven future compatibility |
| Narrative | Kickoff + five progress posts + launch post tagging both accounts; 4–6 min demo; practitioner quote or documented attempt | Three practitioner feedback invitations independently confirmed sent November 2 | **PENDING** — verify existing posts, record 4–6 min video and launch post, and obtain quote permission or document no response |
| Handoff | Final email: live URL, repo, video, docs, config example, issues/future ideas | Working project state, decisions, guides, live app and source repo | **PENDING** — config example/waiver, organizational ownership and final email to Benjamin need closure |

## Gate 7 special benchmarks and sign-off

| Gate 7 benchmark | Status | Evidence / required next action |
|---|---|---|
| Section 13 acceptance checklist fully checked | **PARTIAL** | Quality, public synthetic report, and local setup checks now have evidence; strict worst-site rise, config branding, narrative, organizational ownership and final signoff remain open |
| Practitioner quote (with permission) or documented attempts | **PARTIAL** | Three dated outreach emails sent Nov 2; no practitioner replies established in checked mailbox; log attempts and date of follow-up without fabricating a quote |
| README enables local run in <10 minutes | **PASS on tested Windows machine** | User-run fresh install probe: **5.39 minutes** from Git clone through new Python 3.13 venv, uncached dependency install, imports and temporary Streamlit localhost health. Does not guarantee every machine or full user workflow. JSON/logs held in separate local probe folder |
| Live final demo to Benjamin | **PENDING** | Record date, what was demonstrated and feedback; do not claim attendance/approval in advance |
| 4–6 minute recorded demonstration | **PENDING** | Prepare synthetic-only recording and accessible URL; not yet recorded or published |
| Launch post with live URL and demo video; both tags | **PENDING** | Draft, obtain review, publish then record actual post URL (do not claim published before evidence) |

## Risk register and release decisions

1. **Display precision messaging (CP7.3A):** FIX VERIFIED LOCALLY AND VISUALLY ON PUBLIC APP. The UI now reports a neutral **0.00 percentage-point** difference when both worst-site fill figures display 83.7%, avoiding an unsupported claim of strict improvement. Underlying optimizer output remains unchanged. User-run **488 passed, 17 existing warnings**; hosted synthetic screenshot shows the corrected caption. No independent browser automation was performed.
2. **Strict worst-site benchmark:** Gate 4 original requirement requests an increase. A preserved/equal worst-site fill with improved equity-weighted unmet is analytically defensible, but is **not literal fulfillment**. Ask Benjamin to accept the documented trade-off or identify a permitted alternative. No synthetic manipulation.
3. **Branding from config:** Existing report supports optional bank name and logo inputs; source does not yet show a general YAML/JSON config-based app branding mechanism required in Brief Section 13. Decide on a small nonprofit-only config example or documented waiver, without commercialization.
4. **Privacy/ownership:** Public hosting receives uploaded files on a third-party server; avoid client-level sensitive data. Set an organizational owner for code/deploy/credentials and a maintenance contact before handoff.
5. **Scope:** The software and guide are a free nonprofit contribution; do not build commercial licensing, paid onboarding or client-specific paid deployments. These project constraints are **not** a legal judgment about OPT.

## Suggested final acceptance evidence packet

- User-run post-CP7.3A `python -m pytest -q`: **488 passed, 0 failed, 17 known warnings**; local and public synthetic screens showing neutral 0.00 pp fill-rate delta and public 8-week PDF provenance screenshot. Preserve original evidence separately; these are user-provided, not independent browser test logs.
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

# Week 8 Quick Handoff — Diaper & Period Supply Bank Allocator

**Checkpoint written:** November 6, 2026. **Current known code HEAD:** `de7223dd0cd87df72b103f29613dac9b9145d691` (CP7.4B). Check GitHub `main` again before proposing any patch. **Final target:** November 13, 2026.

## Read first, in this order

1. Benjamin Drury's original ChiEAC Project Brief (scope, acceptance and deadline).
2. Live source in public repository: `https://github.com/trnhokhai/supply-bank-allocator`.
3. `docs/PROJECT_STATE.md` **Section 30** (current status), preserving Sections 1–29 as historical evidence.
4. `docs/acceptance_matrix.md` (PASS/PARTIAL/PENDING and open signoffs).
5. `docs/DECISIONS.md`, especially **Decision 048** (worst-site benchmark and minimal nonprofit report branding).
6. `README.md`, `docs/user_guide.md`, `docs/onboarding_checklist.md`, `docs/methods.md`.

## What is already completed

- Working **free, public, open-source nonprofit** planning application: upload/cleaning, 4–8-week forecasts, equity-aware allocation, Alerts, What-if Scenarios, survey and eight-week single-page synthetic/provenance-labeled funder PDF.
- CP7.1 automatic PDF data-source labels and stale-output safeguards.
- CP7.2 screenshot user guide/onboarding, including separately maintained Word/PDF handoff editions.
- CP7.3A precision fix: **no false claim of strict worst-partner improvement** when displayed delta is `0.00 pp`; optimizer unchanged.
- CP7.3B user-provided public synthetic full planning/PDF screenshots and **5.39-minute** clean Windows/Python 3.13 setup/health probe; 488 local regression passed before CP7.4B.
- CP7.4B `de7223d` nonprofit default report branding via `config/report_branding.json` + staff name/logo overrides. User-reported **508 full tests passed, 0 failed, 17 existing PuLP deprecation warnings; 35 targeted passed**, and local one-page PDF visual PASS with fictitious `Community Test Supply Bank` label. Not a commercial feature.

## What has NOT been verified as complete

- Public Streamlit Cloud workflow **after** CP7.4B `de7223d` deploy.
- Recorded **4–6-minute English product demo video** and its accessible link.
- Published final LinkedIn launch post; earlier required posts need evidence review.
- Formal Benjamin acceptance of the Brief's *strict worst-site fill rise* versus the preserved/unchanged observed result. This is a known deviation; no fabricated uplift.
- ChiEAC organizational repo/deployment ownership/maintenance arrangements, final email, and `v1.0` release tag.
- Real-bank adoption, practitioner feedback, independently measured community need, actual purchases/shipments or true server-cold performance. Three nonprofit outreach messages were verified sent November 2; no replies were verified in the November 5 mailbox review.

## Next safe action sequence

1. Verify latest GitHub HEAD and `git status --short`; don't touch four pre-existing untracked Gate 4 scratch items.
2. Run one synthetic public Cloud smoke for **new CP7.4B branding**: Demo Mode → Clean → Forecast 8w → Allocate 8w → Report with fictitious name → download/inspect one-page provenance-marked PDF. Distinguish local from Cloud evidence.
3. Record/edit short synthetic demo, verify its link.
4. Prepare launch communication + nonprofit documentation/handoff packet, request Benjamin's signoff on the original benchmark deviation and stewardship.
5. Update acceptance/evidence from **actual** outputs only; prepare approved `v1.0` release by Nov 13.

## Rules and guardrails

- No sales, subscriptions, licensing features, paid onboarding, commercial customization or personally funded hosting. The branding config is only a neutral optional nonprofit PDF report default.
- Don't change optimizer to game worst-site result or merge benchmark numbers from different synthetic runs.
- Don't claim that synthetic planning unmet is observed community need, or that modeled units have shipped.
- Don't assume final field validation, ownership transfer, acceptance or publication happened.
- For user local Windows edits, deliver minimal reproducible reviewed patch/ZIP, with `--check` before `--apply`, tests, manual screenshots and selective staging. Do not change GitHub without explicit user agreement; user prefers to review/commit/push themself.

**Working relationship:** Keep explanations compact and practical in informal Vietnamese. Lead technical decisions, avoid repeatedly asking the user to restate prior progress, do not promise background work, and use actual repo/evidence before suggesting work.

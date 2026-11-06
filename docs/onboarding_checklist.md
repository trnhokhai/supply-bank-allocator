# ChiEAC Nonprofit Onboarding Checklist

**Diaper & Period Supply Bank Allocator | Free staff orientation | Draft: November 6, 2026**  
**Live demo:** https://chieac-supply-bank-allocator.streamlit.app/  
**Companion:** [Practical User Guide](user_guide.md)

> **Purpose:** Help staff safely explore the free, public planning tool using synthetic Demo Mode and understand the reviews required before any real operational decision. This is a **free nonprofit handoff aid**, not a paid training package, license or service offer.

## 1. Before the session: facilitator and organization readiness

- [ ] Identify a **planning owner** who understands the distribution log, a **stock owner** who can verify counted inventory and receipts, and an **approver** for any shipment, purchase or funder communication.
- [ ] Open the public URL on a laptop with a modern browser and sufficient connection; keep the **User Guide** nearby.
- [ ] Use **Demo Mode** for the first session. Do not upload client-level, confidential or otherwise sensitive records to public hosting.
- [ ] If later testing organization files, prepare a permission-approved, minimally identifying dataset and verify public-cloud suitability first.
- [ ] Download and inspect the blank CSV templates from Home. Check individual-unit measures, product-size vocabulary, dates, site names/IDs and ZIPs as text.
- [ ] Identify the date of the on-hand inventory snapshot and the owners who can confirm incoming units, dates and status.
- [ ] Establish where the staff will save downloaded CSV/PDF files: the app's survey edits and derived plans are **not** a persistent workspace.
- [ ] Do not assume a positive modeled result authorizes staff to pick, ship, order or make a verified funder claim.

## 2. A 60-minute, free orientation agenda

| Time | Facilitator action | Participant confirmation |
|---|---|---|
| **0–5 min** | Explain the app's purpose, synthetic-vs-real distinction, privacy and human sign-off. | Can explain that forecasts estimate distributions, not measured need. |
| **5–15 min** | Show Home templates, input requirements and common column/size/quantity issues. | Can identify required Distribution Log and inventory need for planning. |
| **15–25 min** | Open Upload; enable Demo Mode; Clean & Validate; inspect corrections and dropped rows. | Can distinguish a cleaned row from a source record verified as accurate. |
| **25–35 min** | Generate an 8-week Forecast; inspect review flags and a single product-size series. | Can explain WAPE, N/A and a provisional plausible range. |
| **35–45 min** | Optimize the 8-week allocation; compare proportional baseline; open Alerts. | Can distinguish ready-now/on-hand from future-inbound-backed allocations and review worst-site fill. |
| **45–53 min** | Run one verified-source -20% donation scenario and show Survey's organization-level form. | Can distinguish hypothetical outcomes from the saved original plan; understands survey save invalidation. |
| **53–60 min** | Generate one-page funder PDF and full SKU CSV; review caveats and next steps. | Can name at least three checks required before using the output outside a demo. |

**Facilitator note:** This is a target outline, **not** a claim that every machine or dataset completes processing within 60 minutes. If an unfamiliar file fails validation, document the blocker; do not bypass data checks to finish on time.

## 3. Practice exercise: a full synthetic planning cycle

1. **Home:** Identify the three-step start and download a blank input template.
2. **Upload:** Enable Demo Mode and click **Clean & Validate**. Review one standardization and one dataset quality summary.
3. **Forecast:** Set **8 weeks**, click **Generate forecast**, identify at least one series or warning requiring review.
4. **Allocate:** Select **8 weeks**, keep worst-partner baseline protection on for the initial demo, click **Optimize allocation**. Name the difference between on-hand-backed and future-inbound-backed units.
5. **Alerts:** Click **Calculate alerts**. Locate both on-hand and projected-cycle WOS and a product-size gap.
6. **Scenarios:** Choose **Community Donations** only, set **-20%**, verify it is a donation source, click **Run what-if scenario**, read the baseline/changed outputs.
7. **Survey:** Inspect both the built-in form and Google Forms CSV import; use only fictitious organizational data. If changing the survey, regenerate the forecast and allocation.
8. **Report:** Create an eight-week PDF, verify its automatic source label and the unknown-price disclosure, then download PDF and CSV.

## 4. Data-quality and interpretation sign-off

| Control | Pass condition | Owner / notes |
|---|---|---|
| Source records | Sources are authorized, organization-level and appropriate for the hosting environment. | __________________ |
| Distribution log | Date, partner, product, size and individual-unit quantities reviewed; missing weeks investigated. | __________________ |
| Current inventory | Dated counts physically reconciled; previously committed units investigated. | __________________ |
| Incoming supply | Status, source, known size and receipt timing confirmed. Pending/late quantities are not silently promoted. | __________________ |
| Partner survey | Organization-only data, ZIP preserved as text, optional equity fields interpreted correctly. | __________________ |
| Forecast | Horizon, selected methods, WAPE provenance, N/A values and flagged series examined. | __________________ |
| Allocation | No presumed shipment; worst-site/proportional comparison read with rounding caveats. | __________________ |
| Alerts | On-hand WOS vs projected-cycle WOS vs full-horizon gaps kept separate. | __________________ |
| Scenarios | Source names and hypothetical-only labels checked; original plan unchanged. | __________________ |
| Report | Eight-week inputs, source label, modeled-vs-observed separation, incomplete costs and disclaimers checked. | __________________ |
| Authorization | Named approver reviews any real pick, purchase, distribution change or external report. | __________________ |

**STOP / escalate** if any of the following apply: suspected personal or confidential data in an upload, wrong/unknown stock snapshot, unverified inbound status, negative/implausible quantities, unreviewed high-impact forecast flags, incomplete price treated as zero, or a funder-facing claim presented as measured community need without supporting evidence.

## 5. After-session handoff

- [ ] Save the synthetic practice PDF and review CSV locally in an approved folder; label both **DEMO / SYNTHETIC**, not organizational impact.
- [ ] Record data issues discovered, proposed corrections, who will verify them and any unresolved access/hosting questions.
- [ ] Agree who maintains the distribution log, inventory snapshot and incoming supply dates at each future planning cycle.
- [ ] Agree who reviews and approves operational allocation drafts and who can publish external reports.
- [ ] If a later approved real-data pilot is proposed, arrange an explicit data/privacy review and consent process first. A demonstration is **not** a validated field pilot.
- [ ] Keep the repository README, [data dictionary](data_dictionary.md), [methods note](methods.md) and [user guide](user_guide.md) as the version-controlled reference set.

**Session record (fill in after training)**

| Field | Record |
|---|---|
| Date / facilitator | ____________________________________ |
| Organization / attendees | ____________________________________ |
| Demo vs approved test files | ____________________________________ |
| Outputs reviewed | ____________________________________ |
| Key corrections / concerns | ____________________________________ |
| Follow-up owner and target date | ____________________________________ |
| Approval for any external or physical action | Not granted by this training document |

## 6. When a question comes up

Use the tool's plain-language warnings first. Consult the **User Guide** for interpretation, `docs/data_dictionary.md` for schema fields and `docs/methods.md` for analytical constraints. For questions about organizational stewardship, hosting/billing or a potential operational pilot, consult the designated ChiEAC project owner. No ongoing paid support or service agreement is implied.

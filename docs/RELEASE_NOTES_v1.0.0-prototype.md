# LISA.ai v1.0.0-prototype Release Notes

- **Release Tag:** `v1.0.0-prototype`
- **Release Date:** August 2026
- **Status:** **FROZEN DEMO RELEASE**
- **Hosted Demo:** [https://lisa-ai-7dtj.onrender.com/](https://lisa-ai-7dtj.onrender.com/)
- **Test Suite Status:** `134 passed` (100% pass rate)

---

## 📌 1. Product Summary

LISA.ai (Life-saving Intelligent Sequencing Assistant) is a clinician-controlled Emergency Department (ED) sequencing and deterioration safety net prototype. Unlike traditional triage which focuses exclusively on static arrival acuity ("How sick is this patient now?"), LISA introduces operational **Risk-of-Wait** modeling ("How does risk change if this patient continues waiting?"), capacity-aware simulated resource allocation, and strict clinician-in-the-loop safety floors.

---

## 🩺 2. Nurse Workstation (FastAPI + HTML5/JS)

The `v1.0.0-prototype` release establishes the high-density, dark-navy Nurse Command Center as the primary demo interface:

- **Command Workspace:** 3-zone live operational layout featuring live priority queue, patient vitals & risk trajectory chart (0–120 min), contributing factors, and clinician decision rail.
- **Capacity Workspace:** Operational view of 8 simulated ED bed spaces (Resus, Monitored, General, Fast-Track) with real-time compatibility assignment and separate tracking for patients awaiting specialized spaces.
- **Evidence Workspace:** Synthetic policy simulator contrasting Static Baseline (Triage Level + FIFO) against LISA Dynamic Sequencing under identical attention capacity (24 slots / 120 min).
- **Audit Workspace:** Session-scoped immutable audit log with event filtering, clinician transitions, override reason codes, clinical justification notes, and version stamps.
- **Governance Workspace:** Transparent implementation matrix contrasting prototype safeguards against the prerequisites for production clinical deployment.

---

## ⚙️ 3. Deterministic Python Core

All scoring, risk forecasting, and sequencing algorithms are implemented in deterministic Python modules without LLM dependencies in the clinical core:

- `lisa/protocol_floor.py`: Deterministic clinical protocol guardrails (Level 1 Resus, Level 2 Emergent).
- `lisa/risk_engine.py`: Multi-horizon Risk-of-Wait trajectory calculation (Now, 30m, 60m, 120m), uncertainty penalties, and reassessment countdown timers.
- `lisa/sequencer.py`: Multi-factor sequence scoring and operational Tier A–E categorization.
- `lisa/allocator.py`: Capacity-aware resource compatibility matching across 8 simulated spaces.
- `lisa/surge_simulator.py`: 3× ED volume surge modeling (60 patients) over constant bed capacity.
- `lisa/baseline_simulator.py`: Static triage level and FIFO baseline comparator.
- `lisa/comparison_metrics.py`: Synthetic policy attention schedule simulator.
- `lisa/audit_log.py`: Append-only audit logger and safety-floor override validator.
- `lisa/governance.py`: Governance specification registry and version constants.

---

## 🛡️ 4. Safety Controls & Human Accountability

- **Inviolable Safety Floors:** Clinical protocol guardrails (Level 1, Level 2) and clinician initial triage levels cannot be downgraded by automated scoring.
- **Clinician Override Protection:** Override attempts that would downgrade protected Level 1 patients below Tier A, or Level 2 patients below Tier B, are strictly blocked by the backend.
- **Audit Preservation:** Clinician decisions (Accept, Escalate, Override) do not overwrite the original system recommendation; both states are preserved in the immutable audit trail.
- **Blocked Event Integrity:** Rejected override attempts generate 0 audit events to prevent cluttering the operational record.

---

## 🏥 5. Capacity Model

Models 8 simulated emergency department resource spaces:
- `B01`: Resuscitation Space (Intubation / Defibrillation / Critical care)
- `B02`–`B03`: Monitored Spaces (Telemetry / Pulse oximetry / Continuous observation)
- `B04`–`B06`: General Treatment Spaces (Standard clinical exam / Observation)
- `B07`–`B08`: Fast-Track Spaces (Ambulatory minor care / Rapid turn)

---

## 📊 6. Simulation Evidence

In the simulated cohort under identical capacity constraints (24 attention slots over 120 min):
- **Normal Mode (20 Patients):** Static baseline generates 1 dynamic-priority inversion; LISA achieves **0 inversions**.
- **Surge Mode (60 Patients):** Static baseline generates 17 dynamic-priority inversions; LISA achieves **0 inversions**.
- **Disclaimer:** *This is a synthetic policy simulation demonstrating attention scheduling order, not clinical efficacy evidence.*

---

## 🔒 7. Privacy, Anti-Bias & Data Minimization

- **100% Synthetic Data:** All records (`A124`–`A183`) are simulated prototype fixtures.
- **Zero Real Identifiers:** Excludes names, phone numbers, home addresses, Aadhaar/SSN numbers, and insurance IDs.
- **Anti-Bias Invariants:** Scoring strictly excludes socioeconomic status, financial class, caste, religion, VIP flags, and payer information.

---

## ⚠️ 8. Known Limitations

1. **Simulated Data Only:** Tested exclusively on synthetic fixture cohorts; real-world patient distributions will vary.
2. **Heuristic Trajectory Model:** Risk-of-Wait trajectories are deterministic heuristic approximations, not validated prospective predictive models.
3. **No Clinical Validation:** Has not undergone randomized controlled trials (RCT) or institutional clinical validation.
4. **Simplified Staffing Assumptions:** Models a single triage attention queue rather than complex multi-disciplinary hospital staffing.
5. **Process-Scoped State:** Audit log and action states reside in process memory; restarts on the free hosting platform reset active session state.
6. **Free Tier Cold Starts:** The hosted demo on Render may take 30–50 seconds to spin up from sleep.
7. **No EHR Integration:** Does not connect to live hospital EHRs (Epic, Cerner), HL7 feeds, or FHIR interfaces.
8. **No Multi-User Auth:** Prototype uses single-role demonstration credentials (`TRIAGE_NURSE_01`) without production RBAC.

---

## 🧪 9. Verification & Test Status

- **Automated Tests:** `134 passed` via `pytest`.
- **Core Modules Diff:** Zero diff on all 9 `lisa/` modules.
- **FastAPI Endpoints:** 100% passing contract tests for `/api/queue`, `/api/patient/{token}`, `/api/allocation`, `/api/comparison`, `/api/audit`, `/api/action/accept`, `/api/action/escalate`, `/api/action/override`, and `/api/governance`.

---

## 🔒 10. Code Freeze Notice

The application codebase for `v1.0.0-prototype` is **frozen**. Any future changes to algorithms, UI, datasets, or backend logic will be released under a new version tag.

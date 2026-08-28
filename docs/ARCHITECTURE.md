# LISA.ai Architecture & System Invariants

**Release:** `v1.0.0-prototype`  
**Status:** Frozen Architecture Specification

---

## 🏛️ 1. High-Level System Architecture

LISA.ai is structured into a clean four-tier pipeline separating presentation, REST bridge, deterministic clinical logic, and synthetic fixtures:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   TIER 1: PRESENTATION LAYER                           │
│  Browser Nurse Command Center (HTML5, Vanilla CSS tokens, JS Client)   │
│  - Command (Live Queue, Patient Inspector, Clinician Decision Rail)    │
│  - Capacity (Simulated ED Spaces, Awaiting Compatible Capacity)        │
│  - Evidence (Static Baseline vs. LISA Policy Simulation)               │
│  - Audit (Session-scoped Clinician Decision Snapshots)                 │
│  - Governance (Implementation Matrix & Safety Invariants)              │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ HTTP / JSON REST API
┌──────────────────────────────────▼─────────────────────────────────────┐
│                   TIER 2: APPLICATION ADAPTER LAYER                    │
│  FastAPI Web Bridge (webapp.py)                                        │
│  - Request validation & Pydantic schema enforcement                    │
│  - Static asset serving (/assets) and single-page routing (/)          │
│  - In-memory session audit management                                  │
│  - Fallback Streamlit Prototype (app.py)                               │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ Python In-Memory API
┌──────────────────────────────────▼─────────────────────────────────────┐
│                   TIER 3: DETERMINISTIC CLINICAL CORE (lisa/)          │
│  - protocol_floor.py     : Immediate Clinical Protocol Guardrails      │
│  - risk_engine.py        : Multi-Horizon Risk-of-Wait Forecasting      │
│  - sequencer.py          : Multi-Factor Priority Scoring & Tiers       │
│  - allocator.py          : Capacity-Aware Space Compatibility          │
│  - surge_simulator.py    : 3x Operational Volume Loader & Metrics      │
│  - baseline_simulator.py : Static Triage + FIFO Comparator Engine      │
│  - comparison_metrics.py : Attention Schedule Simulation (24 slots)    │
│  - audit_log.py          : Clinician Action Validation & Audit Log     │
│  - governance.py         : Governance Specs & Engine Version Registry  │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ CSV File Loading
┌──────────────────────────────────▼─────────────────────────────────────┐
│                   TIER 4: SYNTHETIC DATA FIXTURES (data/)              │
│  - seed_patients.csv  : 20 Normal mode simulated patient intake records │
│  - surge_patients.csv : 60 Surge mode simulated patient intake records │
│  - seed_beds.csv      : 8 simulated ED resource space configurations   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## ⚙️ 2. Module Responsibilities

| Module | Responsibility | Primary Outputs |
|---|---|---|
| `lisa/protocol_floor.py` | Evaluates acute vital/complaint red flags against deterministic clinical rules. | `floor_level` (1 or 2), `triggered`, `reasons`, `hard_floor` flag. |
| `lisa/risk_engine.py` | Computes baseline acuity, projected trajectories (0m, 30m, 60m, 120m), uncertainty penalties, and reassessment countdown timers. | `current_risk`, `risk_30_min`, `risk_60_min`, `risk_120_min`, `confidence`, `recheck_due_min`. |
| `lisa/sequencer.py` | Integrates safety floors, risk trajectories, uncertainty, wait times, and clinician triage to rank patients and assign Tiers A–E. | `priority_rank`, `queue_tier_code`, `sequence_score`, `effective_safety_floor`, `sequence_reasons`. |
| `lisa/allocator.py` | Evaluates clinical needs against 8 simulated ED spaces (Resus, Monitored, General, Fast-Track) using strict capability matching. | `bed_id`, `bed_type`, `allocation_status`, `compatibility_note`, `waiting_patients`. |
| `lisa/surge_simulator.py` | Loads 60-patient cohort, computes pressure ratios (7.5 patients/space), and calculates surge reassessment burdens. | `patient_count`, `bed_count`, `reassess_within_5_min`, `reassess_within_15_min`, `patients_per_bed`. |
| `lisa/baseline_simulator.py` | Implements the traditional ED baseline: Initial Clinician Triage Level + First-In First-Out (FIFO) queue order. | Baseline queue ranking & static tier assignment. |
| `lisa/comparison_metrics.py` | Simulates an identical attention schedule (24 slots of 5 min over 120 min) to evaluate policy efficiency. | `lower_urgency_ahead_of_urgent_count` (inversions), delay metrics, review timeliness percentages. |
| `lisa/audit_log.py` | Validates clinician actions against active safety floors and creates immutable session audit events. | Audit event records, override validation results. |
| `lisa/governance.py` | Maintains deterministic engine version constants and the prototype vs. production governance specification. | Governance dictionary, version registry. |

---

## 🔒 3. Ten Critical System Invariants

The LISA.ai prototype strictly enforces the following ten system invariants:

1. **Protocol Safety Floor Primacy:** Protocol guardrails cannot be downgraded below their calculated floor level (`Level 1` or `Level 2`) by any automated ranking formula or score optimization.
2. **Clinician Level 1 Protection:** An initial clinician triage of `Level 1` guarantees placement in `Tier A` (Immediate Safety Attention) and cannot be lowered by automated scoring.
3. **Clinician Level 2 Protection:** An initial clinician triage of `Level 2` guarantees placement in at least `Tier B` (Emergent Attention) and cannot be lowered by automated scoring.
4. **Physiological Risk Invariance under Surge:** When switching from Normal (20 patients) to Surge (60 patients), the individual clinical inputs and Risk-of-Wait trajectory calculations for original patients remain identical.
5. **Surge as Operational Competition:** Surge changes competition for scarce attention and spaces, not individual patient pathology.
6. **Risk Breach Clock Non-Guarantee:** The reassessment countdown clock indicates operational urgency relative to clinical guidelines; it is **not** a guarantee of safe waiting.
7. **Resource Compatibility Non-Prescription:** Allocator recommendations reflect physical space compatibility (e.g., telemetry access in Monitored space), **not** diagnostic decisions or procedural orders.
8. **Clinician / System Separation in Audit:** Clinician actions (Accept, Escalate, Override) never mutate or overwrite the original system recommendation; both are preserved side-by-side in the immutable audit log.
9. **Zero-Audit on Blocked Actions:** Override attempts blocked by active Level 1 or Level 2 safety floors generate zero successful audit events, preserving audit log cleanliness and integrity.
10. **No LLM in Core Clinical Decision Pipeline:** All clinical risk scoring, protocol guardrails, queue ranking, and resource matching execute via deterministic Python logic without non-deterministic LLM calls.

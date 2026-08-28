# LISA.ai

> **Right Patient. Right Bed. Right Time.**  
> *Prototype simulation only — not for clinical use.*

---

## 📌 Overview

**LISA.ai** (Life-saving Intelligent Sequencing Assistant) is a clinician-controlled Emergency Department (ED) sequencing and deterioration safety net decision-support prototype. It focuses on **Risk-of-Wait**: identifying which waiting patients may become more concerning if delayed, and sequencing limited simulated ED resources accordingly.

- **Traditional Triage Question:** *"How sick is this patient right now?"*
- **LISA's Additional Question:** *"How does operational risk change if this patient continues waiting?"*

### Core Principles & Guardrails
- **No Autonomous Diagnosis:** LISA does not diagnose medical conditions or prescribe treatment.
- **Clinician-in-the-Loop:** Clinicians retain final authority to accept, escalate, or override recommendations.
- **Inviolable Safety Floors:** Protocol guardrails (e.g., Level 1 Resuscitation, Level 2 Emergent) and initial clinician triage floors cannot be downgraded by automated scoring.
- **Deterministic Core:** Deterministic rules and mathematical trajectories drive all scoring and allocation. **No LLM is used in the clinical risk or sequencing core.**
- **Simulated Data Only:** Operates purely on tokenized, synthetic emergency patient scenarios.

---

## 🏗️ System Architecture

```text
       Browser Nurse Workstation (HTML5 / Vanilla JS / CSS)
                                ↓  REST API
                   FastAPI Bridge (webapp.py)
                                ↓
        Deterministic LISA Sequencing & Safety Engines (lisa/)
   ┌──────────────────────┬──────────────────────┬──────────────────────┐
   │ Protocol Guardrails  │ Risk-of-Wait Engine  │  Queue Sequencer     │
   │ (protocol_floor.py)  │   (risk_engine.py)   │    (sequencer.py)    │
   ├──────────────────────┼──────────────────────┼──────────────────────┤
   │ Resource Allocator   │ Surge Simulator (3x) │  Policy Simulator    │
   │   (allocator.py)     │ (surge_simulator.py) │(comparison_metrics.py│
   ├──────────────────────┼──────────────────────┼──────────────────────┤
   │ Clinician Audit Log  │ Governance Registry  │ Baseline Comparator  │
   │   (audit_log.py)     │   (governance.py)    │(baseline_simulator.py│
   └──────────────────────┴──────────────────────┴──────────────────────┘
                                ↓
               Simulated CSV Fixtures (data/)
```

---

## ✨ Implemented Workstation Capabilities

The prototype features a 5-workspace Nurse Command Center designed for operational ED workflows:

1. **COMMAND Workspace:**
   - **3-Zone Live Operational Grid:** Queue overview (rank, token, tier, wait, reassessment), central patient vitals & risk trajectory, and right-rail clinician decision panel.
   - **Risk-of-Wait Trajectories:** Projects deterioration risk at 0m, 30m, 60m, and 120m with confidence scores.
   - **Clinician Decision Rail:** Safety-controlled actions (Accept Recommendation, Escalate Priority, Override System Tier).
   - **Safety Floor Enforcement:** Prevents illegal clinician tier downgrades on protected Level 1 and Level 2 patients.
2. **CAPACITY Workspace:**
   - Operational view of 8 simulated ED bed spaces (Resus, Monitored, General, Fast-Track) with deterministic compatibility matching.
   - Distinct queue separation for patients awaiting higher-capability space versus general queue.
3. **EVIDENCE Workspace:**
   - Simulation-only comparator showing static triage + FIFO baseline vs LISA dynamic sequencing under identical attention capacity (24 slots / 120 min).
   - Highlights reduction of dynamic priority inversions without making clinical efficacy claims.
4. **AUDIT Workspace:**
   - Immutable session-scoped audit trail recording clinician decisions (time, patient, transitions, reasons, notes, version stamps).
5. **GOVERNANCE Workspace:**
   - Full transparency matrix contrasting implemented prototype controls against requirements for prospective clinical validation and real-world deployment.

---

## 🚀 Getting Started

### 1. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 2. Run the Nurse Workstation (Primary Interface)
```bash
uvicorn webapp:app --host 127.0.0.1 --port 8000
```
Open your browser and navigate to:
- **Nurse Command Center:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive OpenAPI Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 3. Legacy / Fallback Streamlit Interface
A standalone Streamlit dashboard is preserved as an alternative inspection tool:
```bash
streamlit run app.py --server.port 8501
```
Navigate to: [http://localhost:8501](http://localhost:8501)

---

## 🧪 Test Suite

Run the automated test suite:
```bash
pytest
```
**Verified Result:** `134 passed`

The test suite validates:
- Protocol guardrails & hard floor enforcement
- Risk-of-Wait trajectory calculations & uncertainty bounds
- Queue sequencing, scoring, and priority ordering
- Capacity-aware simulated space assignments
- 3× Surge mode scalability (60 patients)
- Policy simulation metrics & dynamic priority inversions
- Clinician action validation & append-only audit trail
- Governance invariants & version registry
- FastAPI REST endpoints & contract compliance

---

## 🔍 Key Simulated Demo Cases

- **Patient `A125` (Ambiguous Presentation / Rising Risk):**
  - Starts as initial Level 4 triage. LISA identifies rising risk-of-wait (35 → 49 over 60m), promoting to Tier C without a hard floor constraint. Demonstrates permissible clinician override to Tier B.
- **Patient `A135` (High Acuity / Hard Safety Floor):**
  - Clinician Level 1 triage. Protocol safety floor engages; automated system and clinician override actions are blocked from reducing below Tier A.
- **Patient `A127` (Stable / Low Risk-of-Wait):**
  - Stable vitals and isolated limb injury; assigned Tier E / Tier D with longer reassessment interval, freeing immediate attention slots for deteriorating cases.

---

## 📊 Policy Simulation Evidence

The Evidence workspace demonstrates how dynamic sequencing shifts attention order under **identical physical capacity limits**:
- **Simulated Invariant:** Both policies model the exact same staff (1 triage nurse) and attention slots (24 slots of 5 min over a 120 min window).
- **Observed Behavior:** LISA eliminates simulated dynamic-priority inversions (urgent patients waiting behind lower-urgency patients).
- **Disclaimer:** *This is a synthetic policy simulation, not clinical validation or evidence of medical outcome improvement.*

---

## 🔒 Privacy, Safety & Data Integrity

- **Synthetic Cohort Only:** All records (`A124`–`A183`) are synthetic scenarios generated for research demonstration.
- **No Personal Identifiers:** Zero patient names, phone numbers, addresses, government IDs (e.g. Aadhaar), insurance numbers, or authentic EHR data.
- **Anti-Bias Rules:** Algorithmic scoring strictly excludes demographic, financial, social, and VIP indicators.
- **Deployment Status:** Local prototype currently. Hosted demo deployment instructions will be added separately.

---

## 📁 Repository Structure

```text
lisa-ai/
├── webapp.py                   # FastAPI application & REST endpoints
├── app.py                      # Fallback / legacy Streamlit prototype
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Pytest configuration
├── README.md                   # Project overview & operational guide
├── lisa/                       # Deterministic Python Core
│   ├── protocol_floor.py       # Clinical protocol guardrails engine
│   ├── risk_engine.py          # Risk-of-Wait trajectory engine
│   ├── sequencer.py            # Dynamic queue sequencer & scoring
│   ├── allocator.py            # Capacity-aware resource assignment
│   ├── surge_simulator.py      # 3x Surge simulation loader
│   ├── baseline_simulator.py   # Static triage + FIFO baseline engine
│   ├── comparison_metrics.py   # Policy attention schedule comparator
│   ├── audit_log.py            # Clinician action validation & audit trail
│   └── governance.py           # Governance registry & safety specifications
├── web/                        # Nurse Command Center Frontend
│   ├── command-center.html     # High-density workstation layout
│   └── assets/                 # Workstation styles and client controller
├── data/                       # Synthetic Simulation Fixtures
│   ├── seed_patients.csv       # 20 synthetic patient records (Normal)
│   ├── surge_patients.csv      # 60 synthetic patient records (3x Surge)
│   └── seed_beds.csv           # 8 simulated ED bed spaces
├── docs/                       # Verification Reports & Documentation
│   ├── final_web_qa_report.md  # Milestone 11I QA verification report
│   ├── privacy_and_governance.md # Detailed governance specification
│   └── *.png                   # Workstation reference screenshots
└── tests/                      # Automated pytest suite (134 tests)
```

---

## ⚠️ Disclaimer

This software is an engineering research and educational prototype simulation only. It is **not** validated for medical diagnosis, clinical treatment planning, or hospital bed management.

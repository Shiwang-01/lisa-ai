<img src="web/assets/lisa-app-icon.png" width="90" alt="LISA.ai">

# LISA.ai

**Right Patient. Right Bed. Right Time.**

Clinician-controlled Emergency Department sequencing and Risk-of-Wait decision-support prototype.

> **Prototype simulation only — not for clinical use.**

**[Live Demo](https://lisa-ai-7dtj.onrender.com/)** · **Release: `v1.0.0-prototype`**

*The application source for this release is frozen. Documentation may continue to improve without changing the frozen clinical/operational logic.*

---

![LISA.ai Nurse Command Center](docs/final_brand_command.png)

---

## 📌 The Problem

Emergency departments operate under severe structural constraints:
- Limited physical spaces and specialized monitored beds
- Scarce clinical attention and nurse workload limits
- Incomplete intake information at arrival
- Changing clinical condition while waiting
- Severe surge and volume pressure

Traditional triage primarily answers:
> *"How sick is this patient right now?"*

LISA adds a critical operational question:
> *"How does concern change if this patient continues waiting?"*

---

## ✨ What LISA Does

LISA implements a deterministic, multi-factor sequencing and capacity assignment pipeline:

- **Deterministic Protocol Safety Guardrails:** Immediate hard floors for high-risk presentations (e.g., suspected acute neurological deficit, severe respiratory distress).
- **Risk-of-Wait Trajectory Modeling:** Deterministic risk forecasting across Now, 30m, 60m, and 120m horizons.
- **Confidence & Uncertainty Handling:** Penalizes high clinical uncertainty by shortening reassessment intervals.
- **Reassessment Urgency:** Escalates patients whose safety recheck deadline is approaching or breached.
- **Dynamic Queue Sequencing:** Categorizes patients into operational Tiers A–E based on composite priority scores.
- **Clinician Triage Safety Floor Protection:** Clinician high-acuity triage levels (Level 1 Resuscitation, Level 2 Emergent) are inviolable and cannot be silently downgraded by automated scoring.
- **Capacity-Aware Simulated Resource Allocation:** Matches clinical requirements to compatible simulated ED spaces (Resus, Monitored, General, Fast-Track).
- **Normal & Surge 3× Operational Modes:** Scales from 20 to 60 waiting patients over the same 8 simulated spaces.
- **Clinician Decision Rail:** Human-in-the-loop control with Accept, Escalate, and Override actions.
- **Append-Only Session Audit:** Preserves immutable decision snapshots, version stamps, and clinician notes.
- **Static Baseline vs. LISA Simulation:** Transparent policy simulation under identical attention capacity.
- **Governance & Privacy Transparency:** Clear separation of implemented prototype safeguards versus real-world deployment requirements.

---

## 🚫 What LISA Does NOT Do

To maintain strict clinical safety and operational honesty, LISA explicitly does **NOT**:

- Diagnose patients or identify medical diseases
- Prescribe treatments, medications, or therapy plans
- Autonomously replace triage nurses or clinical staff
- Order laboratory tests, imaging, or diagnostic procedures
- Create hospital capacity or add physical staff
- Claim clinical efficacy or mortality reduction
- Use a Large Language Model (LLM) for the clinical risk or sequencing core
- Represent a certified production hospital deployment

---

## 🩺 Nurse Workstation (5 Workspaces)

The web frontend provides five dedicated operational workspaces:

### 1. Command
The primary operational grid featuring:
- **Left Zone:** Live priority-sequenced queue with real-time risk arrows, wait times, and reassessment countdowns.
- **Center Zone:** Selected patient demographics, vitals, active safety floor context, Risk-of-Wait trajectory chart, and contributing factors.
- **Right Zone:** Clinician decision rail with system recommendation display, resource status, and action buttons (**Accept**, **Escalate**, **Override**).

### 2. Capacity
Operational view of the 8 simulated ED resource spaces showing:
- Real-time compatibility assignments
- Dedicated list of patients awaiting compatible higher-capability space vs. general queue

### 3. Evidence
A policy simulation comparator evaluating Static Baseline (Triage Level + FIFO) against LISA Dynamic Sequencing under **identical attention capacity** (24 attention slots over a 120-minute horizon).

### 4. Audit
Session-scoped immutable audit log displaying every clinician decision, original recommendation snapshot, clinician tier, override reasons, free-text justifications, and engine version stamps.

### 5. Governance
Governance and safety specification matrix contrasting prototype controls against the prerequisites for prospective clinical validation and production deployment.

---

## 👥 Key Demo Patient Scenarios

### Patient `A125` — Rising Risk-of-Wait
- **Profile:** 68F, ambiguous epigastric complaint with profuse diaphoresis, documented diabetes.
- **Initial Clinician Triage:** Level 4 (no hard protocol floor).
- **Risk Trajectory:** 35 → 42 → 49 → 63 (60m projected risk: 49; 120m peak risk: 63; confidence: 82%).
- **Reassessment:** Due in 15 min.
- **Queue Placement:** Promoted to **Tier C** (Priority #13).
- **Clinician Override:** Demonstrates safe clinical override from Tier C to **Tier B** with reason `CLINICAL_APPEARANCE`.

### Patient `A135` — Safety Floor Precedence
- **Profile:** 62F, focal acute neurological presentation.
- **Initial Clinician Triage:** Level 1.
- **Protocol Floor:** Level 2.
- **Effective Operational Safety Floor:** **Level 1** (Clinician triage takes precedence).
- **Queue Placement:** **Tier A** (Priority #1).
- **Safety Lock:** Demonstrates that the automated system and clinician override actions are blocked from downgrading below Tier A.

### Patient `A127` — Low-Risk / Calm State
- **Profile:** 24F, isolated musculoskeletal ankle injury, normal vitals.
- **Risk Trajectory:** Flat / low risk (12 → 12 → 12 → 12).
- **Queue Placement:** **Tier E** / **Tier D** with longer reassessment interval, demonstrating a calm operational state that frees attention for deteriorating patients.

---

## ⚡ Surge Mode (3× Volume)

LISA includes an operational pressure toggle:
- **Normal Mode:** 20 simulated waiting patients across 8 simulated ED resource spaces (2.5 patients/space).
- **Surge 3× Mode:** 60 simulated waiting patients across the same 8 simulated ED resource spaces (7.5 patients/space).

**Operational Invariant:** Surge triples arrival pressure and increases competition for attention and spaces, but **does not alter an individual patient's underlying physiological Risk-of-Wait calculation**.

> **More demand. Same capacity.**

---

## 📊 Policy Simulation Evidence

The Evidence workspace demonstrates the sequencing effect of dynamic prioritization under identical constraints:

| Operational Metric | Static Baseline (Normal / Surge) | LISA Dynamic Policy (Normal / Surge) |
|---|---|---|
| **Dynamic Priority Inversions** | 1 / 17 | **0 / 0** |
| **High Wait-Risk Reviewed ≤ 30m** | 100% / 40% | **100% / 80%** |
| **Urgent Cohort Reviewed ≤ 15m** | 50% / 17% | **100% / 100%** |
| **Protocol Floor Reviewed ≤ 5m** | 100% / 0% | **100% / 100%** |
| **Available Attention Slots** | 24 slots (Same Capacity) | 24 slots (Same Capacity) |

> **Simulation result — not clinical efficacy evidence.**

*LISA does not create additional nurses, beds, or attention slots; it dynamically sequences scarce attention to eliminate priority inversions in the simulated cohort.*

---

## 🛡️ Clinician Control & Human Accountability

LISA separates system recommendations from clinician authority:

> **"LISA recommends. The clinician decides. The system remembers why."**

- **System Recommendation:** Preserved immutably in the audit record.
- **Clinician Decision:** Authority to Accept, Escalate (one tier upward), or Override.
- **Safety Invariant:** Level 1 and Level 2 safety floors strictly block unsafe operational downgrades.
- **Audit Trace:** Records timestamp, acting role (`TRIAGE_NURSE_01`), mode, transitions, reason codes, notes, and engine versions (`LISA-RoW-v0.7`, `LISA-Demo-Rules-v1`, `LISA-SEQ-v1`).

---

## 🏥 Simulated Capacity Model

LISA sequences placement across **8 simulated ED resource spaces**:

- `B01` — **Resuscitation Space** (Intubation, mechanical ventilation, defibrillation)
- `B02` — **Monitored Space** (Continuous telemetry, pulse oximetry, non-invasive BP)
- `B03` — **Monitored Space** (Continuous telemetry, pulse oximetry, non-invasive BP)
- `B04` — **General Treatment Space** (Standard examination, wound care, basic observation)
- `B05` — **General Treatment Space** (Standard examination, wound care, basic observation)
- `B06` — **General Treatment Space** (Standard examination, wound care, basic observation)
- `B07` — **Fast-Track Space** (Minor ambulatory injuries, rapid discharge observation)
- `B08` — **Fast-Track Space** (Minor ambulatory injuries, rapid discharge observation)

*These are simulated resource types for capacity matching, not live hospital bed telemetry feeds.*

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
               Synthetic CSV Fixtures (data/)
```

**Architectural Invariant:** No LLM is used in the clinical risk, guardrail, or sequencing core.

---

## 🚀 Run Locally

### 1. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 2. Start the Nurse Workstation (Primary Interface)
```bash
uvicorn webapp:app --host 127.0.0.1 --port 8000
```
Open your browser to:
- **Nurse Command Center:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive OpenAPI Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 3. Legacy / Fallback Streamlit Interface
A standalone Streamlit dashboard is preserved as an alternative inspection tool:
```bash
streamlit run app.py --server.port 8501
```
Open: [http://localhost:8501](http://localhost:8501)

---

## 🧪 Automated Testing

Run the automated test suite:
```bash
pytest
```
**Verified Release Result:** `134 passed`

Test coverage areas:
- Protocol guardrail rules & safety floor enforcement
- Risk-of-Wait trajectory calculations & uncertainty bounds
- Dynamic queue sequencing, scoring, and priority ordering
- Capacity-aware space compatibility assignments
- 3× Surge mode scalability & invariant checks
- Policy simulation metrics & dynamic priority inversion checks
- Clinician action validation & append-only audit trail
- Governance specifications & deterministic version trace
- FastAPI REST integration & contract validation

---

## 🔒 Privacy, Anti-Bias & Governance

- **100% Synthetic Data:** All patient records (`A124`–`A183`) are simulated scenarios.
- **Zero Personal Identifiers:** Excludes names, phone numbers, home addresses, government identifiers (e.g. Aadhaar), insurance IDs, and authentic EHR data.
- **Explicitly Excluded Factors:** The scoring and allocation algorithms strictly exclude:
  - Insurance / payer status
  - Payment ability / financial class
  - Socioeconomic status
  - Caste, ethnicity, or race
  - Religion
  - VIP / celebrity status
  - Hospital donation history
  - Expected revenue value
  - Room / suite preference

*Note: Algorithmic design minimizes demographic bias, but this does not constitute a mathematical guarantee that all bias has been eliminated.*

---

## ⚠️ Production Boundary & Regulatory Disclaimers

This prototype establishes clear boundaries regarding real-world healthcare deployment:

- **Not Clinically Proven:** Requires multi-center prospective clinical trials and ethical review before clinical adoption.
- **Prototype Architecture:** Lacks institutional single sign-on (SSO), role-based access control (RBAC), encrypted persistent database storage, and real-time HL7/FHIR EHR interfaces.
- **Regulatory Status:** This prototype is **not** FDA approved, CE marked, ABDM certified, HIPAA compliant, GDPR compliant, or DPDP certified.
- **Intended Use:** Engineering research, educational demonstration, and healthcare innovation prototyping only.

---

## 🌐 Hosted Demo

- **URL:** [https://lisa-ai-7dtj.onrender.com/](https://lisa-ai-7dtj.onrender.com/)
- **Infrastructure Note:** Hosted as a prototype demonstration on a free cloud instance. The instance may experience a 30–50 second cold start on initial access. Action and audit states are session-scoped and reset upon service restart.

---

## 📦 Release

- **Current Release:** `v1.0.0-prototype`
- **Freeze Policy:** Application source code is frozen. Any subsequent functional modifications will be released under a new version tag.

---

## 📚 Documentation Index

- [Architecture & Invariants](docs/ARCHITECTURE.md)
- [Release Notes (v1.0.0-prototype)](docs/RELEASE_NOTES_v1.0.0-prototype.md)
- [Demo Script (4:30 Walkthrough)](docs/final_demo_script.md)
- [Live Demo Checklist](docs/demo_checklist.md)
- [Final Web QA Report](docs/final_web_qa_report.md)
- [Project Status](docs/PROJECT_STATUS.md)
- [Privacy & Governance Specification](docs/privacy_and_governance.md)

---

## 📁 Repository Structure

```text
.
├── webapp.py                   # FastAPI application & REST endpoints
├── app.py                      # Legacy / fallback Streamlit prototype
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Pytest configuration
├── README.md                   # Project overview & documentation
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
│   ├── ARCHITECTURE.md         # System architecture & critical invariants
│   ├── RELEASE_NOTES_v1.0.0-prototype.md # Official release notes
│   ├── final_demo_script.md    # 4-minute 30-second presentation script
│   ├── demo_checklist.md       # Pre-presentation verification checklist
│   ├── final_web_qa_report.md  # Comprehensive QA verification report
│   ├── PROJECT_STATUS.md       # Freeze declaration and status
│   └── privacy_and_governance.md # Governance & privacy specifications
└── tests/                      # Automated pytest suite (134 tests)
```

---

## ⚠️ Disclaimer

LISA.ai is a simulation and decision-support prototype intended for research, education, and innovation demonstration. It has not been clinically validated and must **not** be used for real patient care.

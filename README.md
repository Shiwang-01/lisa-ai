# LISA.ai — Life-saving Intelligent Sequencing Assistant

> **Dynamic ED Sequencing + Deterioration Safety Net**  
> *Prototype simulation only — not for clinical use.*

---

## 📌 Overview

**LISA.ai** is a clinician-controlled emergency department (ED) sequencing and deterioration safety net prototype designed to assist healthcare providers in identifying waiting patients at risk of rapid decompensation.

- **Traditional Triage Question:** *"How sick is this patient right now?"*
- **LISA's Additional Question:** *"How dangerous could it become for this patient to keep waiting?"*

The prototype runs locally using simulated data and does not require external clinical systems or LLM APIs.

---

## 🏗️ Architecture & Completed Milestones

1. **Milestone 1:** 20-patient synthetic Streamlit foundation (`A124`–`A143`).
2. **Milestone 2:** Deterministic Clinical Protocol Guardrails (`Level 1` & `Level 2` hard floors).
3. **Milestone 3:** Deterministic Risk-of-Wait Engine (Current, 30m, 60m, 120m risk trajectory, uncertainty, breach urgency).
4. **Milestone 4:** Dynamic Operational Queue Sequencer (Tiers A–E, Sequence Score, explainable reason codes).
5. **Milestone 5:** Capacity-Aware Bed Allocation (8 simulated spaces across Resus, Monitored, General, Fast-track).
6. **Milestone 6A:** Deterministic 3× ED Surge Mode (60 synthetic patients `A124`–`A183`).
7. **Milestone 6B / 6B.1:** Queue Policy Simulation (Static Triage vs LISA) with Clinician Triage Safety Floors.
8. **Milestone 7:** Human-in-the-Loop Clinician Actions (Accept, Escalate, Override) & Append-Only Audit Trail.
9. **Milestone 8:** Privacy, Governance & Safety Panel (`docs/privacy_and_governance.md`).

---

## 🔒 Privacy, Safety & Governance

- **Decision-Support Only:** LISA does not diagnose, prescribe treatment, or autonomously admit/discharge patients.
- **Clinician in Control:** Human clinicians retain final decision-making authority; system recommendations can be accepted, escalated, or overridden.
- **Inviolable Safety Floors:** Clinical protocol guardrails and clinician high-acuity triage levels cannot be downgraded by automated scoring.
- **Data Minimization:** Uses tokenized synthetic IDs only (`A124`–`A183`). Strictly excludes names, contact numbers, Aadhaar, insurance, and billing data.
- **Anti-Bias Invariant:** Excludes financial, demographic, caste, religion, and VIP status from all scoring and allocation logic.
- **Append-Only Auditability:** Session-scoped audit log records full context, version stamps, and human actions.
- **Regulatory Disclaimers:** Prototype design assumptions only. No claims of DPDP, HIPAA, GDPR compliance, ABDM certification, FDA approval, or formal clinical validation.

*For complete governance specifications, see [`docs/privacy_and_governance.md`](docs/privacy_and_governance.md).*

---

## 🚀 Getting Started

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Tests
```bash
pytest
```

### 3. Run Streamlit Application
```bash
streamlit run app.py
```

---

## 📁 Repository Structure
```
lisa-ai/
├── app.py                      # Main Streamlit clinical & governance dashboard
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Pytest configuration
├── README.md                   # Project overview & governance summary
├── docs/
│   └── privacy_and_governance.md # Formal privacy & governance specification
├── data/
│   ├── seed_patients.csv       # 20 simulated emergency patient records (Normal)
│   ├── surge_patients.csv      # 60 simulated emergency patient records (3x Surge)
│   └── seed_beds.csv           # 8 simulated emergency department bed spaces
├── lisa/
│   ├── protocol_floor.py       # Clinical Protocol Guardrails engine
│   ├── risk_engine.py          # Risk-of-Wait trajectory modeling engine
│   ├── sequencer.py            # Dynamic Queue Sequencer & Safety Floor logic
│   ├── allocator.py            # Capacity-Aware Bed Allocation engine
│   ├── surge_simulator.py      # 3x Surge simulation loader & summary
│   ├── baseline_simulator.py   # Static triage/FIFO baseline queue engine
│   ├── comparison_metrics.py   # Queue policy attention schedule simulator
│   ├── audit_log.py            # Clinician actions & append-only audit trail
│   └── governance.py           # Privacy, safety, and governance specification
└── tests/                      # 115+ automated unit and integration tests
```

---

## ⚠️ Disclaimer
This software is an engineering research and educational prototype simulation only. It is **not** validated for medical diagnosis or clinical decision support.

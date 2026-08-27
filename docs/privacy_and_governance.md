# LISA.ai — Privacy, Safety & Governance Specification

> ⚠️ **IMPORTANT PROTOTYPE DISCLAIMER**  
> LISA.ai is an engineering research prototype and operational sequencing decision-support tool. It is **not for clinical use** and is **not a diagnostic or treatment prescription system**.  
>  
> This document details prototype design assumptions, implemented engineering safeguards, and necessary production governance targets. **No claim is made of DPDP compliance, HIPAA compliance, GDPR compliance, ABDM certification, FDA approval, or formal clinical validation.** Any real-world deployment would require formal legal, clinical, cybersecurity, and statutory regulatory review.

---

## 1. Prototype Scope & Clinical Safety Positioning

The prototype runs locally using simulated data and does not require external clinical systems, hospital EHR connections, or external LLM APIs.

LISA operates strictly under a **human-in-the-loop decision-support** paradigm:
- **No Diagnosis:** LISA evaluates operational wait risk and physiological escalation patterns; it never generates diagnostic labels or syndrome conclusions.
- **No Autonomous Treatment:** LISA never prescribes medications, procedures, investigations, or clinical interventions.
- **No Autonomous Discharge or Admission:** LISA recommends queue order and compatible bed spaces; clinicians retain final authority on all patient placements.
- **Safety Floors are Inviolable:** Automated heuristics and clinician overrides can escalate operational urgency, but cannot downgrade active clinical protocol guardrails or clinician-assigned high-acuity tiers.

---

## 2. Implemented Prototype Controls vs Production Requirements

| Governance Domain | Implemented in Prototype | Production Deployment Requirement |
|---|---|---|
| **Patient Identification** | Tokenized synthetic IDs (`A124`–`A183`) only; zero patient names, contact numbers, or home addresses. | Production-grade patient identity and pseudonymization strategy appropriate to deployment. |
| **Authentication & Access** | Fixed simulated clinician role (`TRIAGE_NURSE_01`) for demonstration. | Production authentication, multi-factor authentication (MFA) where appropriate, and role-based / attribute-based access controls (RBAC/ABAC). |
| **Data Encryption** | In-memory simulated runtime structures. | Production-grade encryption in transit and at rest with secure key management. |
| **Audit Trail Storage** | In-memory append-only session-scoped audit log. | Durable, access-controlled, tamper-evident audit storage. |
| **Clinical Rules & Governance** | Deterministic protocol floors (`LISA-Demo-Rules-v1`) and heuristic risk engine (`LISA-RoW-v0.7`). | Hospital clinical governance approval, prospective clinical validation, and continuous Root Cause Analysis (RCA). |
| **Data Integration** | Pre-loaded synthetic CSV cohorts (20-patient normal & 60-patient 3× surge). | Hospital electronic health record (EHR) connectivity where applicable. |
| **Consent & Lifecycle** | Purely synthetic data; no live patient data processed. | Patient consent management, dynamic privacy notice workflows, and cryptographic data deletion governance where appropriate. |

---

## 3. Data Minimization & Privacy Invariants

LISA adheres strictly to data minimization principles:
- **Captured Information:** Only clinically and operationally necessary parameters (vital signs, age, wait duration, categorical symptom presentations, and physiological distress markers).
- **Strictly Excluded Identifiers:**
  - Patient names and aliases
  - Phone numbers and email addresses
  - Physical street addresses and GPS coordinates
  - National identifiers (Aadhaar, Passport, PAN, Voter ID)
  - Social media and family contact identifiers

---

## 4. Excluded Prioritization Features (Anti-Bias Invariant)

Under no circumstances may operational queue sequencing, risk scoring, or bed allocation reference or weight:
1. **Financial & Insurance Status:** Payment ability, insurance carrier, billing class, payer category, or deposit amount.
2. **Socioeconomic Demographics:** Caste, religion, socioeconomic status, ethnicity, or nationality.
3. **Institutional Favoritism:** VIP status, executive relationships, donor history, or hospital revenue impact.

*Automated test suites (`tests/test_governance.py`) continuously scan all algorithm source files to verify that these attributes are absent from scoring and allocation logic.*

---

## 5. Subgroup Fairness Monitoring Plan

LISA does not claim to be "unbiased." In a production hospital setting, continuous algorithmic fairness monitoring should be performed across:
- **Age Subgroups:** Parity across pediatric (<18y), adult (18–64y), and geriatric (≥65y) presentations.
- **Sex-Based Subgroups:** Monitoring triage urgency calibration and queue wait distributions using the collected sex field. Additional demographic dimensions should only be monitored in production where they are lawfully and appropriately collected.
- **Complaint Phrasing & Language:** Robustness against language variation and regional complaint expressions.
- **Missing-History Resilience:** Ensuring patients without prior hospital records are not systematically deprioritized relative to patients with complete histories.
- **Clinician Override Disparities:** Monitoring whether clinician override frequencies vary significantly across demographic cohorts.

---

## 6. Human Accountability Chain

```
Simulated Intake Findings
        ↓
Clinical Protocol Guardrails (Hard Floors)
        ↓
Risk-of-Wait Engine (Trajectory Modeling)
        ↓
Dynamic Queue Sequencer & Bed Allocator
        ↓
Transparent Reason Codes & Safety Floor Display
        ↓
Human Clinician Review (Accept / Escalate / Override)
        ↓
Immutable Clinical Audit Event Logged
        ↓
Human Clinician Retains Final Accountability
```

---

## 7. Model, Rule, and Engine Versioning

| Component | Engine Type | Prototype Version | Scope & Responsibility |
|---|---|:---:|---|
| **Clinical Protocol Guardrails** | Deterministic hard rules | `LISA-Demo-Rules-v1` | Critical physiological thresholds, airway compromise, stroke-like signs |
| **Risk-of-Wait Engine** | Deterministic heuristic simulation | `LISA-RoW-v0.7` | Risk trajectory (0m, 30m, 60m, 120m), confidence, breach urgency |
| **Dynamic Queue Sequencer** | Deterministic operational logic | `LISA-SEQ-v1` | Tier mapping (A–E), sequence scoring, safety floor sorting |
| **Bed Capacity Allocator** | Deterministic compatibility matching | `LISA-ALLOC-v1` | 8-bed allocation, scarce-resource preservation, waiting queue |

---

## 8. Regulatory Design Assumptions

### India Deployment Focus
- **Guiding Principles:** High-level alignment with the principles of the **Digital Personal Data Protection Act, 2023 (DPDP)** and the **Ayushman Bharat Digital Mission (ABDM)** Health Data Management Policy.
- **Status:** Prototype design assumption only. Any prospective hospital pilot in India would require formal legal review, data protection impact assessments, institutional ethics committee clearance, and statutory cybersecurity audit. No DPDP compliance or ABDM certification is claimed.

### International Considerations
- **Guiding Frameworks:** High-level architectural awareness of **HIPAA / HITECH** (US) and **GDPR / EU AI Act** (EU).
- **Status:** Concept-level design consideration. Formal Software-as-a-Medical-Device (SaMD) classifications and jurisdiction-specific conformity assessments would be required. No HIPAA, GDPR, or FDA clearance is claimed.

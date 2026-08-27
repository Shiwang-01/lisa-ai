"""LISA.ai — Privacy, Governance & Safety Specification (Milestone 8)

Deterministic governance model defining:
1. Implemented prototype safety and privacy controls
2. Unimplemented production requirements
3. Data minimization standards and strictly excluded prioritization features
4. Human accountability and auditability mechanisms
5. Subgroup fairness monitoring targets
6. Regulatory and jurisdiction design assumptions

IMPORTANT DISCLAIMER:
This is a prototype design assumption and governance target.
LISA does NOT claim DPDP compliance, HIPAA compliance, GDPR compliance,
ABDM certification, FDA approval, or formal clinical validation.
Any real deployment would require formal legal, clinical, cybersecurity,
and regulatory review before use.
"""

from typing import Any, Dict, List

from lisa.audit_log import MODEL_VERSION, RULE_VERSION, SEQUENCER_VERSION

ALLOCATOR_VERSION = "LISA-ALLOC-v1"

# Prohibited Prioritization Features
EXCLUDED_PRIORITIZATION_FEATURES = [
    "insurance_status",
    "payment_ability",
    "socioeconomic_class",
    "caste",
    "religion",
    "vip_status",
    "donation_history",
    "hospital_revenue_value",
    "billing_class",
    "payer_type",
    "room_category_preference"
]

def get_governance_summary() -> Dict[str, Any]:
    """Returns structured, deterministic privacy, governance, and safety metadata.

    Returns:
        Dict containing all formal governance sections and comparisons.
    """
    return {
        "clinical_safety_position": {
            "statement": "LISA is a sequencing decision-support prototype.",
            "principles": [
                "LISA does not diagnose.",
                "LISA does not prescribe treatment or procedures.",
                "LISA does not autonomously discharge, admit, or allocate care.",
                "LISA may escalate operational concern but cannot violate active safety floors.",
                "Final prioritization and clinical decisions remain strictly with human clinicians."
            ]
        },
        "implemented_prototype_controls": [
            "Simulated patient cohort only — zero real-world patient records",
            "Tokenized synthetic identifiers (e.g. A124–A183) — no patient names or contact info",
            "No Aadhaar numbers, national identity IDs, or insurance identifiers stored",
            "Deterministic clinical protocol guardrails (Level 1 / Level 2 hard floors)",
            "Deterministic Risk-of-Wait heuristic trajectory engine (Current, 30m, 60m, 120m)",
            "Clinician Triage Safety Floor — clinician high-acuity assignments cannot be downgraded",
            "Human-in-the-loop actions: Accept Recommendation, Escalate Urgency, and Override",
            "Mandatory clinical reasoning requirement for all operational overrides",
            "Hard safety-floor override enforcement — prohibited tier downgrades are blocked",
            "Append-only session-scoped clinical audit trail capturing full decision context",
            "Model, rule, and sequencer version stamping on every audit event",
            "Explainable sequence and resource reason codes provided with every recommendation"
        ],
        "unimplemented_production_requirements": [
            "Production authentication, MFA where appropriate, and role-based/attribute-based access controls",
            "Production-grade patient identity and pseudonymization strategy appropriate to deployment",
            "Production-grade encryption in transit and at rest with secure key management",
            "Durable, access-controlled, tamper-evident audit storage",
            "Hospital electronic health record (EHR) connectivity where applicable",
            "Patient consent management and dynamic privacy notice workflows where appropriate",
            "Production data retention, scheduled archival, and cryptographic data deletion governance",
            "Automated enterprise backup, disaster recovery, and business continuity procedures",
            "Continuous security monitoring, intrusion detection, and third-party vulnerability assessments",
            "Formal legal, clinical governance, ethics review, and statutory regulatory evaluation before deployment"
        ],
        "implemented_vs_required_matrix": [
            {
                "domain": "Patient Identification",
                "prototype_status": "Tokenized synthetic IDs only",
                "prototype_badge": "Prototype implemented",
                "production_requirement": "Production-grade patient identity / pseudonymization strategy appropriate to deployment",
                "production_badge": "Production requirement"
            },
            {
                "domain": "Access & Authentication",
                "prototype_status": "Simulated single role (TRIAGE_NURSE_01)",
                "prototype_badge": "Prototype implemented",
                "production_requirement": "Production authentication, MFA where appropriate, and role-based/attribute-based access controls",
                "production_badge": "Production requirement"
            },
            {
                "domain": "Audit Trail Storage",
                "prototype_status": "Append-only session-scoped state",
                "prototype_badge": "Prototype implemented",
                "production_requirement": "Durable, access-controlled, tamper-evident audit storage",
                "production_badge": "Production requirement"
            },
            {
                "domain": "Clinical Safety Floors",
                "prototype_status": "Hard deterministic protocol & clinician triage floors",
                "prototype_badge": "Prototype implemented",
                "production_requirement": "Hospital clinical governance approval and prospective clinical validation",
                "production_badge": "Production requirement"
            },
            {
                "domain": "Data Encryption",
                "prototype_status": "In-memory simulated runtime structures",
                "prototype_badge": "Prototype implemented",
                "production_requirement": "Production-grade encryption in transit and at rest with secure key management",
                "production_badge": "Production requirement"
            },
            {
                "domain": "Regulatory Status",
                "prototype_status": "Engineering simulation prototype (not for clinical use)",
                "prototype_badge": "Prototype implemented",
                "production_requirement": "Formal legal, clinical, cybersecurity, and regulatory review before deployment",
                "production_badge": "Production requirement"
            }
        ],
        "data_minimization_rules": [
            "LISA processes only clinically and operationally relevant simulated features (vitals, complaint, distress, wait time).",
            "Patient names, phone numbers, home addresses, emails, and social handles are strictly excluded.",
            "Government identification numbers (Aadhaar, Passport, PAN, Voter ID) are strictly excluded.",
            "Financial, billing, insurance policy, and payment transaction data are strictly excluded.",
            "No unneeded demographic or commercial fields are captured or stored in runtime structures."
        ],
        "excluded_prioritization_features": EXCLUDED_PRIORITIZATION_FEATURES,
        "fairness_monitoring_dimensions": [
            "Age group performance parity (pediatric <18y, adult 18–64y, geriatric ≥65y)",
            "Sex-based subgroup monitoring (using collected sex field; additional demographic dimensions to be monitored in production only where lawfully and appropriately collected)",
            "Complaint language format and symptom description variation robustness",
            "Missing-history robustness (records available vs unavailable disparity analysis)",
            "Clinician override rate equity across presentation subgroups",
            "Reassessment deadline breach rate parity across arrival time cohorts",
            "Systematic under-prioritization and over-prioritization monitoring"
        ],
        "human_accountability_chain": [
            "1. Intake Findings & Vitals Recorded",
            "2. Deterministic Protocol Floors & Risk-of-Wait Trajectory Computed",
            "3. Dynamic Operational Queue & Resource Recommendation Generated",
            "4. Transparent Reason Codes & Effective Safety Floor Displayed",
            "5. Human Clinician Evaluates Recommendation (Retains Full Authority)",
            "6. Action Taken: Accept Recommendation, Escalate Urgency, or Override",
            "7. Immutable Audit Event Appended with Both System & Clinician Context",
            "8. Clinician Remains Strictly Accountable for Final Patient Care"
        ],
        "regulatory_design_assumptions": {
            "india_focus": {
                "frameworks": "Digital Personal Data Protection Act, 2023 (DPDP) & Ayushman Bharat Digital Mission (ABDM) Health Data Management Policy principles",
                "disclaimer": "Prototype design assumption only. Any real deployment in India would require formal legal, privacy, clinical, and cybersecurity review against applicable law and health-data governance requirements. No DPDP compliance or ABDM certification is claimed."
            },
            "international_expansion": {
                "frameworks": "HIPAA / HITECH (United States), GDPR / EU AI Act (European Union)",
                "disclaimer": "Prototype design assumption only. International deployment would require jurisdiction-specific legal review, Data Protection Impact Assessments (DPIA), and Software-as-a-Medical-Device (SaMD) regulatory evaluation. No HIPAA, GDPR, or FDA clearance is claimed."
            }
        },
        "model_and_rule_versions": [
            {
                "component": "Clinical Protocol Guardrails",
                "engine_type": "Deterministic hard-rule engine",
                "version": RULE_VERSION,
                "scope": "Airway, severe distress, stroke-like signs, critical physiological thresholds"
            },
            {
                "component": "Risk-of-Wait Engine",
                "engine_type": "Deterministic heuristic simulation",
                "version": MODEL_VERSION,
                "scope": "Current, 30m, 60m, 120m risk, confidence, time-to-breach, recheck deadlines"
            },
            {
                "component": "Dynamic Queue Sequencer",
                "engine_type": "Deterministic operational prioritization",
                "version": SEQUENCER_VERSION,
                "scope": "Two-stage tier mapping, sequence scoring, safety floor sorting precedence"
            },
            {
                "component": "Bed Capacity Allocator",
                "engine_type": "Deterministic compatibility logic",
                "version": ALLOCATOR_VERSION,
                "scope": "8-bed matching, scarce-resource preservation, waiting queue status"
            }
        ],
        "data_flow_steps": [
            "Simulated Intake",
            "Clinical Guardrails",
            "Risk-of-Wait Engine",
            "Queue Sequencer",
            "Resource Allocator",
            "Clinician Review",
            "Audit Event Recording"
        ]
    }

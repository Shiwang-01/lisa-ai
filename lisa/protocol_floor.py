"""LISA.ai — Clinical Protocol Guardrail Layer (Milestone 2)

Deterministic, explainable safety-rule layer that establishes a PROTOCOL FLOOR.
Answers: "Does this patient have a hard red flag that prevents them from being treated as low urgency?"
"""

from typing import Any, Dict, List, Optional, Union
import pandas as pd


def evaluate_protocol_floor(patient: Union[Dict[str, Any], pd.Series]) -> Dict[str, Any]:
    """Evaluates deterministic clinical protocol guardrails for a patient presentation.

    Args:
        patient: Dictionary or Pandas Series containing patient attributes.

    Returns:
        Structured result dictionary:
        {
            "triggered": bool,
            "floor_level": int or None (1-5),
            "reasons": list of str,
            "rule_ids": list of str
        }
    """
    triggered_rules: List[Dict[str, Any]] = []

    # Safely extract and normalize fields
    def get_str(field: str) -> str:
        val = patient.get(field, "")
        if pd.isna(val) or val is None:
            return ""
        return str(val).strip()

    def get_num(field: str, default: float = -1.0) -> float:
        val = patient.get(field, default)
        try:
            if pd.isna(val) or val is None:
                return default
            return float(val)
        except (ValueError, TypeError):
            return default

    complaint = get_str("complaint_text").lower()
    case_notes = get_str("case_notes").lower()
    known_history = get_str("known_history").lower()
    mental_status = get_str("mental_status").lower()
    visible_distress = get_str("visible_distress").lower()
    pregnancy_status = get_str("pregnancy_status").lower()
    resource_need = get_str("resource_need").lower()

    combined_text = f"{complaint} {case_notes} {resource_need} {known_history}".lower()

    age = get_num("age", -1)
    spo2 = get_num("spo2", -1)
    respiratory_rate = get_num("respiratory_rate", -1)
    systolic_bp = get_num("systolic_bp", -1)
    temperature = get_num("temperature", -1)

    # -------------------------------------------------------------------------
    # RULE: GF-CRITICAL-01 (Protocol Floor: Level 1)
    # Extreme instability: unresponsive, severe airway collapse, catastrophic bleed
    # -------------------------------------------------------------------------
    is_unresponsive = mental_status in ["unresponsive", "comatose"]
    is_catastrophic_bleed = any(k in combined_text for k in ["catastrophic bleeding", "exsanguinating", "massive hemorrhage"])
    is_complete_airway_obstruction = any(k in combined_text for k in ["complete airway obstruction", "severe stridor with cyanosis", "apnea"])

    if is_unresponsive or is_catastrophic_bleed or is_complete_airway_obstruction:
        triggered_rules.append({
            "rule_id": "GF-CRITICAL-01",
            "floor_level": 1,
            "reason": "Immediate critical instability documented"
        })

    # -------------------------------------------------------------------------
    # RULE: GF-RESP-01 (Protocol Floor: Level 2)
    # Severe respiratory concern: SpO2 <= 90 or documented severe respiratory distress
    # -------------------------------------------------------------------------
    has_severe_hypoxia = 0 < spo2 <= 90
    has_severe_resp_distress = (
        ("breathlessness" in combined_text or "respiratory distress" in combined_text or "asthma" in combined_text)
        and (respiratory_rate >= 30 or visible_distress == "severe")
    )

    if has_severe_hypoxia or has_severe_resp_distress:
        triggered_rules.append({
            "rule_id": "GF-RESP-01",
            "floor_level": 2,
            "reason": "Severe respiratory concern / low oxygen saturation"
        })

    # -------------------------------------------------------------------------
    # RULE: GF-STROKE-01 (Protocol Floor: Level 2)
    # Stroke-like symptoms: facial droop, slurred speech, sudden focal neuro deficit
    # -------------------------------------------------------------------------
    stroke_keywords = ["facial droop", "slurred speech", "focal neurologic", "stroke team", "hemiparesis", "aphasia"]
    if any(kw in combined_text for kw in stroke_keywords):
        triggered_rules.append({
            "rule_id": "GF-STROKE-01",
            "floor_level": 2,
            "reason": "Stroke-like symptoms documented"
        })

    # -------------------------------------------------------------------------
    # RULE: GF-BLEED-01 (Protocol Floor: Level 2)
    # Active significant bleeding documented
    # -------------------------------------------------------------------------
    bleed_keywords = ["active bleeding", "active bleed", "bright red oozing", "deep cut with active bleeding", "deep laceration"]
    if any(kw in combined_text for kw in bleed_keywords) and "bleeding" in combined_text:
        triggered_rules.append({
            "rule_id": "GF-BLEED-01",
            "floor_level": 2,
            "reason": "Active bleeding documented"
        })

    # -------------------------------------------------------------------------
    # RULE: GF-PREG-01 (Protocol Floor: Level 2)
    # Pregnancy with bleeding documented
    # -------------------------------------------------------------------------
    is_pregnant = "pregnant" in pregnancy_status or "gestation" in known_history or "pregnant" in combined_text
    has_preg_bleeding = "bleeding" in combined_text or "hemorrhage" in combined_text
    if is_pregnant and has_preg_bleeding:
        triggered_rules.append({
            "rule_id": "GF-PREG-01",
            "floor_level": 2,
            "reason": "Pregnancy with bleeding"
        })

    # -------------------------------------------------------------------------
    # RULE: GF-MENTAL-01 (Protocol Floor: Level 2)
    # Altered mental status / confusion / lethargy / unresponsiveness
    # -------------------------------------------------------------------------
    has_altered_mental_status = (
        mental_status in ["confused", "lethargic", "altered", "disoriented", "unresponsive"]
        or "acute confusion" in combined_text
        or "altered sensorium" in combined_text
        or "altered mental status" in combined_text
    )
    if has_altered_mental_status:
        triggered_rules.append({
            "rule_id": "GF-MENTAL-01",
            "floor_level": 2,
            "reason": "Altered mental status"
        })

    # -------------------------------------------------------------------------
    # RULE: GF-PEDS-01 (Protocol Floor: Level 2)
    # Young pediatric patient with BOTH fever AND lethargy / reduced responsiveness
    # -------------------------------------------------------------------------
    if 0 <= age < 18:
        has_fever = temperature >= 38.0 or "fever" in combined_text
        has_lethargy = (
            mental_status in ["lethargic", "unresponsive", "altered"]
            or "lethargy" in combined_text
            or "lethargic" in combined_text
            or "poor oral intake" in combined_text
        )
        if has_fever and has_lethargy:
            triggered_rules.append({
                "rule_id": "GF-PEDS-01",
                "floor_level": 2,
                "reason": "Pediatric fever with lethargy"
            })

    # -------------------------------------------------------------------------
    # RULE: GF-AIRWAY-01 (Protocol Floor: Level 2)
    # Potential airway compromise (lip/tongue swelling + allergy, drooling + foreign object)
    # -------------------------------------------------------------------------
    has_allergy_swelling = (
        any(k in combined_text for k in ["lip swelling", "swelling of lips", "swollen lips", "tongue swelling", "swelling of tongue", "angioedema"])
        and any(a in combined_text for a in ["allergy", "allergic", "allergen", "rash", "urticaria", "urticarial", "epinephrine", "anaphylaxis"])
    )
    has_foreign_body_airway = (
        "drooling" in combined_text
        and any(f in combined_text for f in ["foreign object", "swallowed", "stridor", "foreign body"])
    )
    has_airway_watch = "airway assessment" in combined_text or "airway observation" in combined_text

    if has_allergy_swelling or has_foreign_body_airway or has_airway_watch:
        triggered_rules.append({
            "rule_id": "GF-AIRWAY-01",
            "floor_level": 2,
            "reason": "Potential airway compromise"
        })

    # -------------------------------------------------------------------------
    # RULE: GF-SHOCK-01 (Protocol Floor: Level 2)
    # Severe hypotension (SBP < 90) + confusion, marked distress, or fever
    # -------------------------------------------------------------------------
    if 0 < systolic_bp < 90:
        has_shock_presentation = (
            mental_status in ["confused", "lethargic", "altered"]
            or visible_distress in ["moderate", "severe"]
            or temperature >= 38.0
            or (0 < temperature < 36.0)
            or "sepsis" in combined_text
        )
        if has_shock_presentation:
            triggered_rules.append({
                "rule_id": "GF-SHOCK-01",
                "floor_level": 2,
                "reason": "Hypotension with concerning presentation"
            })

    # -------------------------------------------------------------------------
    # Aggregation & Conflict Resolution (Most urgent floor wins)
    # -------------------------------------------------------------------------
    if not triggered_rules:
        return {
            "triggered": False,
            "floor_level": None,
            "reasons": [],
            "rule_ids": []
        }

    # Minimum floor_level integer represents highest clinical urgency (e.g. 1 > 2 > 3)
    best_floor = min(r["floor_level"] for r in triggered_rules)
    
    # Deduplicate rule IDs and reasons while preserving order
    seen_ids = set()
    rule_ids = []
    reasons = []

    for r in triggered_rules:
        if r["rule_id"] not in seen_ids:
            seen_ids.add(r["rule_id"])
            rule_ids.append(r["rule_id"])
            reasons.append(r["reason"])

    return {
        "triggered": True,
        "floor_level": best_floor,
        "reasons": reasons,
        "rule_ids": rule_ids
    }

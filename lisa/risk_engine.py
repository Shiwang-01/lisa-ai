"""LISA.ai — Risk-of-Wait Engine (Milestone 3)

Deterministic, explainable heuristic engine that evaluates patient Risk of Waiting:
"How concerning could continued waiting become for this patient?"

Calculates:
1. Current Risk (0-100)
2. 30-min Wait Risk (0-100)
3. 60-min Wait Risk (0-100)
4. 120-min Wait Risk (0-100)
5. Confidence (0-100)
6. Deterioration Slope (points / 30 min)
7. Estimated Risk Breach Clock (minutes to reach threshold 75)
8. Reassessment Deadline (minutes)
9. Risk Band ("Low", "Moderate", "High", "Critical")
10. Human-readable Risk and Uncertainty Factors + Explanation Codes
"""

from typing import Any, Dict, List, Optional, Union
import pandas as pd

# =============================================================================
# CONFIGURABLE THRESHOLDS & WEIGHTS
# =============================================================================
RISK_BREACH_THRESHOLD = 75

BAND_LOW_MAX = 29
BAND_MODERATE_MAX = 49
BAND_HIGH_MAX = 74

BASE_RISK = 5

# Vital signs weights
WEIGHT_SPO2_CRITICAL = 26      # SpO2 <= 91%
WEIGHT_SPO2_MODERATE = 14      # SpO2 92 - 94%

WEIGHT_RR_CRITICAL = 20        # RR >= 30 (adult) or >= 34 (child)
WEIGHT_RR_MODERATE = 12        # RR >= 24 (adult) or >= 28 (child)

WEIGHT_HR_MARKED = 18          # HR > 130 bpm
WEIGHT_HR_MODERATE = 10        # HR 105 - 130 bpm
WEIGHT_HR_BRADY = 12           # HR < 50 bpm

WEIGHT_BP_HYPOTENSION = 24     # SBP < 90 mmHg
WEIGHT_BP_MILD_HYPO = 10       # SBP 90 - 100 mmHg
WEIGHT_BP_SEVERE_HYPER = 14    # SBP >= 180 mmHg

WEIGHT_FEVER_HIGH = 10         # Temp >= 39.0 °C
WEIGHT_FEVER_MOD = 6           # Temp >= 38.0 °C

# Age vulnerability weights
WEIGHT_AGE_YOUNG_CHILD = 8     # Age < 5
WEIGHT_AGE_OLDER_CHILD = 4     # Age 5 - 17
WEIGHT_AGE_ELDERLY = 10        # Age >= 75
WEIGHT_AGE_OLDER_ADULT = 6     # Age 65 - 74

# Neurological / Mental Status weights
WEIGHT_MENTAL_UNRESPONSIVE = 35
WEIGHT_MENTAL_ALTERED = 20

# Distress weights
WEIGHT_DISTRESS_SEVERE = 14
WEIGHT_DISTRESS_MODERATE = 7

# Pain weights (low contribution, pain alone does not create urgency)
WEIGHT_PAIN_HIGH = 5           # Pain score 8 - 10
WEIGHT_PAIN_MOD = 2            # Pain score 4 - 7

# Protocol Guardrail contribution
WEIGHT_GUARDRAIL_L1 = 40
WEIGHT_GUARDRAIL_L2 = 18
FLOOR_MIN_RISK_L1 = 85
FLOOR_MIN_RISK_L2 = 52


def evaluate_risk_of_wait(
    patient: Union[Dict[str, Any], pd.Series],
    protocol_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Calculates deterministic Risk-of-Wait trajectory and uncertainty for a patient.

    Args:
        patient: Dictionary or Pandas Series containing patient attributes.
        protocol_result: Result dictionary from evaluate_protocol_floor, or None.

    Returns:
        Structured dictionary with risk scores, slope, breach clock, reassessment time,
        and human/machine explanation factors.
    """
    # Safe field extractors
    def get_str(field: str) -> str:
        val = patient.get(field, "")
        if pd.isna(val) or val is None:
            return ""
        return str(val).strip()

    def get_num(field: str, default: Optional[float] = None) -> Optional[float]:
        val = patient.get(field, None)
        if val is None or pd.isna(val) or val == "":
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    complaint = get_str("complaint_text").lower()
    case_notes = get_str("case_notes").lower()
    known_history = get_str("known_history").lower()
    mental_status = get_str("mental_status").lower()
    visible_distress = get_str("visible_distress").lower()
    pregnancy_status = get_str("pregnancy_status").lower()
    prior_records = get_str("prior_record_available").lower()
    resource_need = get_str("resource_need").lower()

    combined_text = f"{complaint} {case_notes} {resource_need} {known_history}".lower()

    age = get_num("age", None)
    spo2 = get_num("spo2", None)
    respiratory_rate = get_num("respiratory_rate", None)
    systolic_bp = get_num("systolic_bp", None)
    diastolic_bp = get_num("diastolic_bp", None)
    heart_rate = get_num("heart_rate", None)
    temperature = get_num("temperature", None)
    pain_score = get_num("pain_score", None)

    risk_factors: List[str] = []
    uncertainty_factors: List[str] = []
    explanation_codes: List[str] = []

    # Baseline emergency department triage evaluation
    explanation_codes.append("RW-BASELINE")
    risk_factors.append("Emergency department baseline triage assessment")

    # =========================================================================
    # PART 1: CURRENT RISK CALCULATION
    # =========================================================================
    current_risk_acc = float(BASE_RISK)

    # A. Vitals: SpO2
    if spo2 is not None:
        if spo2 <= 91:
            current_risk_acc += WEIGHT_SPO2_CRITICAL
            explanation_codes.append("RW-VITAL-SPO2")
            risk_factors.append(f"High respiratory concern: severe hypoxia (SpO2 {int(spo2)}%)")
        elif spo2 <= 94:
            current_risk_acc += WEIGHT_SPO2_MODERATE
            explanation_codes.append("RW-VITAL-SPO2")
            risk_factors.append(f"Moderate respiratory concern: borderline oxygen saturation (SpO2 {int(spo2)}%)")

    # B. Vitals: Respiratory Rate
    if respiratory_rate is not None:
        is_peds = age is not None and age < 12
        crit_rr = 34 if is_peds else 30
        mod_rr = 28 if is_peds else 24
        if respiratory_rate >= crit_rr:
            current_risk_acc += WEIGHT_RR_CRITICAL
            explanation_codes.append("RW-VITAL-RR")
            risk_factors.append(f"Marked tachypnea (respiratory rate {int(respiratory_rate)}/min)")
        elif respiratory_rate >= mod_rr:
            current_risk_acc += WEIGHT_RR_MODERATE
            explanation_codes.append("RW-VITAL-RR")
            risk_factors.append(f"Elevated respiratory rate ({int(respiratory_rate)}/min)")

    # C. Vitals: Heart Rate
    if heart_rate is not None:
        if heart_rate > 130:
            current_risk_acc += WEIGHT_HR_MARKED
            explanation_codes.append("RW-VITAL-HR")
            risk_factors.append(f"Marked tachycardia (heart rate {int(heart_rate)} bpm)")
        elif heart_rate >= 105:
            current_risk_acc += WEIGHT_HR_MODERATE
            explanation_codes.append("RW-VITAL-HR")
            risk_factors.append(f"Moderate tachycardia (heart rate {int(heart_rate)} bpm)")
        elif heart_rate < 50:
            current_risk_acc += WEIGHT_HR_BRADY
            explanation_codes.append("RW-VITAL-HR")
            risk_factors.append(f"Bradycardia (heart rate {int(heart_rate)} bpm)")

    # D. Vitals: Blood Pressure
    if systolic_bp is not None:
        if systolic_bp < 90:
            current_risk_acc += WEIGHT_BP_HYPOTENSION
            explanation_codes.append("RW-VITAL-BP")
            risk_factors.append(f"Hypotension / hemodynamic compromise (SBP {int(systolic_bp)} mmHg)")
        elif systolic_bp <= 100:
            current_risk_acc += WEIGHT_BP_MILD_HYPO
            explanation_codes.append("RW-VITAL-BP")
            risk_factors.append(f"Borderline low blood pressure (SBP {int(systolic_bp)} mmHg)")
        elif systolic_bp >= 180:
            current_risk_acc += WEIGHT_BP_SEVERE_HYPER
            explanation_codes.append("RW-VITAL-BP")
            risk_factors.append(f"Severe hypertensive blood pressure elevation (SBP {int(systolic_bp)} mmHg)")

    # E. Vitals: Temperature
    if temperature is not None:
        if temperature >= 39.0:
            current_risk_acc += WEIGHT_FEVER_HIGH
            explanation_codes.append("RW-VITAL-TEMP")
            risk_factors.append(f"High fever ({temperature:.1f} °C)")
        elif temperature >= 38.0:
            current_risk_acc += WEIGHT_FEVER_MOD
            explanation_codes.append("RW-VITAL-TEMP")
            risk_factors.append(f"Fever ({temperature:.1f} °C)")

    # F. Age Vulnerability
    if age is not None:
        if age < 5:
            current_risk_acc += WEIGHT_AGE_YOUNG_CHILD
            explanation_codes.append("RW-AGE-PEDS")
            risk_factors.append(f"High age vulnerability: young infant/child ({int(age)} yrs)")
        elif age < 18:
            current_risk_acc += WEIGHT_AGE_OLDER_CHILD
            explanation_codes.append("RW-AGE-PEDS")
            risk_factors.append(f"Pediatric vulnerability ({int(age)} yrs)")
        elif age >= 75:
            current_risk_acc += WEIGHT_AGE_ELDERLY
            explanation_codes.append("RW-AGE-GERI")
            risk_factors.append(f"High geriatric vulnerability ({int(age)} yrs)")
        elif age >= 65:
            current_risk_acc += WEIGHT_AGE_OLDER_ADULT
            explanation_codes.append("RW-AGE-GERI")
            risk_factors.append(f"Older adult vulnerability ({int(age)} yrs)")

    # G. Mental Status
    if mental_status in ["unresponsive", "comatose"]:
        current_risk_acc += WEIGHT_MENTAL_UNRESPONSIVE
        explanation_codes.append("RW-MENTAL")
        risk_factors.append("Critical unresponsive mental status")
    elif mental_status in ["confused", "lethargic", "altered", "disoriented"] or "altered mental status" in combined_text:
        current_risk_acc += WEIGHT_MENTAL_ALTERED
        explanation_codes.append("RW-MENTAL")
        risk_factors.append(f"Altered mental status / reduced sensorium ({mental_status.capitalize()})")

    # H. Visible Distress
    if visible_distress == "severe":
        current_risk_acc += WEIGHT_DISTRESS_SEVERE
        explanation_codes.append("RW-DISTRESS")
        risk_factors.append("Severe visible physiological or clinical distress")
    elif visible_distress == "moderate":
        current_risk_acc += WEIGHT_DISTRESS_MODERATE
        explanation_codes.append("RW-DISTRESS")
        risk_factors.append("Moderate visible distress")

    # I. Pain
    if pain_score is not None:
        if pain_score >= 8:
            current_risk_acc += WEIGHT_PAIN_HIGH
            explanation_codes.append("RW-PAIN")
            risk_factors.append(f"Severe acute pain score ({int(pain_score)}/10)")
        elif pain_score >= 4:
            current_risk_acc += WEIGHT_PAIN_MOD
            explanation_codes.append("RW-PAIN")

    # J. Clinical Symptoms & Presentation Red Flags
    # 1. Stroke-like signs
    stroke_terms = ["facial droop", "slurred speech", "focal neurologic", "stroke", "hemiparesis"]
    if any(k in combined_text for k in stroke_terms):
        current_risk_acc += 22
        explanation_codes.append("RW-SYMPTOM")
        risk_factors.append("Stroke-like signs documented (facial droop / slurred speech)")

    # 2. Severe respiratory complaint
    if any(k in combined_text for k in ["breathlessness", "asthma exacerbation", "severe wheezing"]) and "RW-VITAL-SPO2" not in explanation_codes:
        current_risk_acc += 16
        explanation_codes.append("RW-SYMPTOM")
        risk_factors.append("Documented severe acute respiratory complaint")

    # 3. Bleeding
    if "active bleeding" in combined_text or "bright red oozing" in combined_text:
        current_risk_acc += 18
        explanation_codes.append("RW-SYMPTOM")
        risk_factors.append("Active external bleeding documented")

    # 4. Pregnancy with bleeding
    is_pregnant = "pregnant" in pregnancy_status or "gestation" in known_history
    if is_pregnant and ("bleeding" in combined_text or "vaginal bleeding" in combined_text):
        current_risk_acc += 20
        explanation_codes.append("RW-SYMPTOM")
        risk_factors.append("Pregnancy with documented vaginal bleeding")

    # 5. Airway compromise
    has_allergy_swelling = (
        any(k in combined_text for k in ["lip swelling", "swelling of lips", "tongue swelling"])
        and any(a in combined_text for a in ["allergy", "rash", "urticaria", "urticarial", "peanut"])
    )
    has_foreign_body = "drooling" in combined_text and any(f in combined_text for f in ["foreign object", "swallowed", "stridor"])
    if has_allergy_swelling or has_foreign_body:
        current_risk_acc += 20
        explanation_codes.append("RW-SYMPTOM")
        risk_factors.append("Potential airway compromise / upper airway concern documented")

    # 6. Ambiguous high-risk presentation (A125: "gas/acidity", sweating, diabetes)
    has_gas_acidity = any(g in combined_text for g in ["gas", "acidity", "gastric burning", "epigastric"])
    has_diaphoresis = any(s in combined_text for s in ["sweating", "diaphoresis", "cold sweat"])
    if has_gas_acidity and has_diaphoresis:
        current_risk_acc += 22
        explanation_codes.append("RW-SYMPTOM")
        risk_factors.append("Older adult with ambiguous chest/upper-abdominal discomfort")
        risk_factors.append("Sweating reported")
        if "diabetes" in known_history:
            risk_factors.append("Diabetes history documented")
        risk_factors.append("Continued waiting produces increasing simulated risk")

    # 7. Acute abdomen
    if "abdominal pain" in combined_text and ("rebound" in combined_text or "worsening" in combined_text):
        current_risk_acc += 14
        explanation_codes.append("RW-SYMPTOM")
        risk_factors.append("Progressive acute abdominal presentation")

    # 8. Severe headache
    if any(h in combined_text for h in ["thunderclap", "severe headache", "worst headache"]):
        current_risk_acc += 14
        explanation_codes.append("RW-SYMPTOM")
        risk_factors.append("Sudden severe thunderclap-type headache")

    # 9. Acute gastroenteritis / dehydration (A143)
    if any(d in combined_text for d in ["vomiting", "diarrhea", "dehydrated", "dehydration"]):
        current_risk_acc += 10
        explanation_codes.append("RW-SYMPTOM")
        risk_factors.append("Acute volume depletion / gastroenteritis with dehydration risk")

    # 10. Vague weakness presentation (A132)
    if "vague" in combined_text and "weakness" in combined_text:
        current_risk_acc += 8
        explanation_codes.append("RW-SYMPTOM")
        risk_factors.append("Generalized weakness with unlocalized etiology")

    # 11. Chest tightness / anxiety presentation (A134)
    if "chest tightness" in combined_text or "anxious" in combined_text:
        current_risk_acc += 6
        explanation_codes.append("RW-SYMPTOM")
        risk_factors.append("Acute chest tightness with physiological stress/anxiety")

    # 12. Respiratory tract symptoms without hypoxia (A139)
    if any(c in combined_text for c in ["cough", "fever/cough", "respiratory tract"]) and "RW-VITAL-SPO2" not in explanation_codes:
        current_risk_acc += 5
        explanation_codes.append("RW-SYMPTOM")
        risk_factors.append("Mild respiratory infection symptoms without hypoxia")

    # K. Protocol Guardrail Integration
    if protocol_result and protocol_result.get("triggered"):
        fl = protocol_result.get("floor_level", 2)
        if fl == 1:
            current_risk_acc += WEIGHT_GUARDRAIL_L1
            current_risk_acc = max(current_risk_acc, float(FLOOR_MIN_RISK_L1))
            explanation_codes.extend(["RW-GUARDRAIL", "RW-GUARDRAIL-L1"])
            risk_factors.append("Clinical guardrail active: Level 1 Critical safety floor")
        elif fl == 2:
            current_risk_acc += WEIGHT_GUARDRAIL_L2
            current_risk_acc = max(current_risk_acc, float(FLOOR_MIN_RISK_L2))
            explanation_codes.extend(["RW-GUARDRAIL", "RW-GUARDRAIL-L2"])
            risk_factors.append("Clinical guardrail active: Level 2 Emergent safety floor")

    current_risk = int(round(min(100.0, max(0.0, current_risk_acc))))

    # =========================================================================
    # PART 2: CONFIDENCE CALCULATION
    # =========================================================================
    confidence_acc = 100.0

    # Missing vitals penalties
    missing_vitals_count = 0
    if spo2 is None:
        missing_vitals_count += 1
    if systolic_bp is None:
        missing_vitals_count += 1
    if heart_rate is None:
        missing_vitals_count += 1
    if respiratory_rate is None:
        missing_vitals_count += 1

    if missing_vitals_count > 0:
        confidence_acc -= (missing_vitals_count * 12.0)
        explanation_codes.append("CF-MISSING-VITALS")
        uncertainty_factors.append(f"Incomplete vital signs recorded ({missing_vitals_count} missing)")

    # Missing prior records
    if prior_records in ["no", "false", "0"]:
        confidence_acc -= 20.0
        explanation_codes.append("CF-NO-PRIOR-RECORD")
        uncertainty_factors.append("No prior hospital medical records available")

    # Limited / unconfirmed history
    if any(h in known_history for h in ["unknown", "none reported"]) and prior_records in ["no", "false", "0"]:
        confidence_acc -= 10.0
        explanation_codes.append("CF-LIMITED-HISTORY")
        uncertainty_factors.append("Medical history unconfirmed / zero-history patient")

    # Ambiguous or vague complaint
    if has_gas_acidity and has_diaphoresis:
        confidence_acc -= 18.0
        explanation_codes.append("CF-AMBIGUOUS-COMPLAINT")
        uncertainty_factors.append("Ambiguous symptom description increases uncertainty")
    elif "vague" in combined_text or "weakness" in complaint:
        confidence_acc -= 18.0
        explanation_codes.append("CF-VAGUE-COMPLAINT")
        uncertainty_factors.append("Vague, non-specific chief complaint without clear localization")

    # Missing mental status
    if not mental_status:
        confidence_acc -= 10.0
        explanation_codes.append("CF-MISSING-MENTAL-STATUS")
        uncertainty_factors.append("Mental status assessment missing")

    confidence = int(round(min(100.0, max(0.0, confidence_acc))))

    # =========================================================================
    # PART 3: DETERIORATION SLOPE
    # =========================================================================
    # Check if stable low-acuity control
    is_stable_low_acuity = (
        any(inj in combined_text for inj in ["ankle sprain", "knee injury", "twisted right ankle", "twisted left knee"])
        and (visible_distress in ["none", "mild"] or not visible_distress)
        and (spo2 is None or spo2 >= 98)
        and (respiratory_rate is None or respiratory_rate <= 16)
        and (systolic_bp is None or (110 <= systolic_bp <= 130))
        and not (protocol_result and protocol_result.get("triggered"))
    )

    if is_stable_low_acuity:
        deterioration_slope = 0.5
        explanation_codes.append("DS-STABLE-LOW-ACUITY")
    else:
        slope_acc = 2.0  # background progression

        if "RW-VITAL-SPO2" in explanation_codes or any(k in combined_text for k in ["breathlessness", "asthma"]):
            slope_acc += 6.0
            explanation_codes.append("DS-RESPIRATORY")
        if any(k in combined_text for k in stroke_terms):
            slope_acc += 6.5
            explanation_codes.append("DS-NEURO")
        if has_allergy_swelling or has_foreign_body:
            slope_acc += 6.5
            explanation_codes.append("DS-AIRWAY")
        if is_pregnant and ("bleeding" in combined_text or "vaginal bleeding" in combined_text):
            slope_acc += 6.0
            explanation_codes.append("DS-PREG-BLEED")
        if "active bleeding" in combined_text or "bright red oozing" in combined_text:
            slope_acc += 5.5
            explanation_codes.append("DS-BLEEDING")
        if "RW-MENTAL" in explanation_codes:
            slope_acc += 5.0
            explanation_codes.append("DS-MENTAL")
        if "RW-VITAL-BP" in explanation_codes and systolic_bp is not None and systolic_bp < 90:
            slope_acc += 5.5
            explanation_codes.append("DS-HEMODYNAMIC")
        if age is not None and age < 18 and "RW-VITAL-TEMP" in explanation_codes and "RW-MENTAL" in explanation_codes:
            slope_acc += 6.0
            explanation_codes.append("DS-PEDS-FEVER")
        if has_gas_acidity and has_diaphoresis:
            slope_acc += 4.5
            explanation_codes.append("DS-AMBIGUOUS-PRESENTATION")
        if any(w in combined_text for w in ["worsening", "vomiting and watery diarrhea", "dehydrated"]):
            slope_acc += 3.5
            explanation_codes.append("DS-WORSENING")

        deterioration_slope = round(min(12.0, max(0.5, slope_acc)), 2)

    # =========================================================================
    # PART 4: FUTURE RISK TRAJECTORY (30, 60, 120 min)
    # =========================================================================
    uncertainty_frac = (100.0 - confidence) / 100.0

    def calc_future_risk(t_min: float) -> int:
        t_units = t_min / 30.0
        uncert_boost = uncertainty_frac * 2.5 * t_units
        projected = current_risk + (deterioration_slope * t_units) + uncert_boost
        return int(round(min(100.0, max(float(current_risk), projected))))

    risk_30_raw = calc_future_risk(30.0)
    risk_60_raw = calc_future_risk(60.0)
    risk_120_raw = calc_future_risk(120.0)

    # Strict monotonicity guarantee: current <= 30 <= 60 <= 120
    risk_30 = max(current_risk, min(100, risk_30_raw))
    risk_60 = max(risk_30, min(100, risk_60_raw))
    risk_120 = max(risk_60, min(100, risk_120_raw))

    # =========================================================================
    # PART 5: RISK BAND
    # =========================================================================
    if current_risk <= BAND_LOW_MAX:
        risk_band = "Low"
    elif current_risk <= BAND_MODERATE_MAX:
        risk_band = "Moderate"
    elif current_risk <= BAND_HIGH_MAX:
        risk_band = "High"
    else:
        risk_band = "Critical"

    # =========================================================================
    # PART 6: RISK BREACH CLOCK
    # =========================================================================
    time_to_breach_min: Optional[int] = None

    if current_risk >= RISK_BREACH_THRESHOLD:
        time_to_breach_min = 0
    elif risk_120 < RISK_BREACH_THRESHOLD:
        time_to_breach_min = None
    else:
        # Interpolate between time intervals
        timeline = [(0, current_risk), (30, risk_30), (60, risk_60), (120, risk_120)]
        for i in range(len(timeline) - 1):
            t0, r0 = timeline[i]
            t1, r1 = timeline[i + 1]
            if r0 < RISK_BREACH_THRESHOLD <= r1:
                fraction = (RISK_BREACH_THRESHOLD - r0) / max(1, (r1 - r0))
                time_to_breach_min = int(round(t0 + fraction * (t1 - t0)))
                time_to_breach_min = max(1, min(120, time_to_breach_min))
                break

    # =========================================================================
    # PART 7: REASSESSMENT DEADLINE
    # =========================================================================
    # Deterministic mapping based on risk band, protocol floor, and confidence
    is_protocol_triggered = bool(protocol_result and protocol_result.get("triggered"))
    fl = protocol_result.get("floor_level") if protocol_result else None

    if fl == 1 or current_risk >= 75:
        recheck_due_min = 5
    elif fl == 2:
        recheck_due_min = 5 if (current_risk >= 65 or deterioration_slope >= 6.0) else 10
    elif risk_band == "High":
        recheck_due_min = 10 if (confidence < 75 or deterioration_slope >= 5.0) else 15
    elif risk_band == "Moderate":
        recheck_due_min = 15 if (confidence < 75 or deterioration_slope >= 4.0) else 30
    else:
        # Low risk band
        recheck_due_min = 45 if confidence < 80 else 60

    # Ensure deduplicated explanation codes
    seen_codes = set()
    deduped_codes = []
    for c in explanation_codes:
        if c not in seen_codes:
            seen_codes.add(c)
            deduped_codes.append(c)

    return {
        "current_risk": current_risk,
        "risk_30_min": risk_30,
        "risk_60_min": risk_60,
        "risk_120_min": risk_120,
        "confidence": confidence,
        "deterioration_slope": deterioration_slope,
        "time_to_breach_min": time_to_breach_min,
        "recheck_due_min": recheck_due_min,
        "risk_band": risk_band,
        "risk_factors": risk_factors,
        "uncertainty_factors": uncertainty_factors,
        "explanation_codes": deduped_codes
    }

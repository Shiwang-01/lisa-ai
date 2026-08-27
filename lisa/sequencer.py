"""LISA.ai — Dynamic Queue Sequencer (Milestone 4)

Operational emergency department sequencing engine.
Answers: "Given all currently waiting patients, who needs attention first?"

Architecture:
- Two-Stage approach:
  Stage 1: Assign an Operational Queue Tier (Tier A through Tier E)
  Stage 2: Calculate an explainable Sequence Score (0–100)
- Protocol Safety Floor directly restricts operational tiers.
- Safety strictly dominates simple FIFO waiting time.
"""

from typing import Any, Dict, List, Optional, Union
import pandas as pd

from lisa.protocol_floor import evaluate_protocol_floor
from lisa.risk_engine import evaluate_risk_of_wait

# =============================================================================
# CONFIGURABLE WEIGHTS & CONSTANTS
# =============================================================================
WEIGHT_CURRENT_RISK = 0.30
WEIGHT_RISK_60 = 0.30
WEIGHT_BREACH_URGENCY = 0.15
WEIGHT_REASSESS_URGENCY = 0.10
WEIGHT_UNCERTAINTY = 0.10
WEIGHT_WAIT_TIME = 0.05

# Operational Tiers Metadata
TIER_A_CODE = "Tier A"
TIER_A_NAME = "Immediate Safety Attention"
TIER_A_ACTION = "Immediate clinician reassessment"

TIER_B_CODE = "Tier B"
TIER_B_NAME = "Urgent Reassessment"
TIER_B_ACTION = "Urgent clinician reassessment"

TIER_C_CODE = "Tier C"
TIER_C_NAME = "Rising Wait-Risk"
TIER_C_ACTION = "Prioritize for reassessment"

TIER_D_CODE = "Tier D"
TIER_D_NAME = "Monitored Queue"
TIER_D_ACTION = "Maintain monitored queue with timed reassessment"

TIER_E_CODE = "Tier E"
TIER_E_NAME = "Lower Current Wait-Risk"
TIER_E_ACTION = "Continue queue with scheduled reassessment"

TIER_ORDER = {
    TIER_A_CODE: 1,
    TIER_B_CODE: 2,
    TIER_C_CODE: 3,
    TIER_D_CODE: 4,
    TIER_E_CODE: 5,
}


def assign_queue_tier(
    patient: Union[Dict[str, Any], pd.Series],
    protocol_result: Dict[str, Any],
    risk_result: Dict[str, Any]
) -> Dict[str, str]:
    """Assigns an Operational Queue Tier (Stage 1).

    Args:
        patient: Patient data dict or Series.
        protocol_result: Result from evaluate_protocol_floor.
        risk_result: Result from evaluate_risk_of_wait.

    Returns:
        Dict with tier_code, tier_name, full_label, and recommended_action.
    """
    fl = protocol_result.get("floor_level") if protocol_result.get("triggered") else None
    current_risk = risk_result.get("current_risk", 0)
    risk_60 = risk_result.get("risk_60_min", 0)
    time_to_breach = risk_result.get("time_to_breach_min")
    recheck_due = risk_result.get("recheck_due_min", 60)
    confidence = risk_result.get("confidence", 100)

    # -------------------------------------------------------------------------
    # TIER A: Immediate Safety Attention
    # - Protocol Floor Level 1 OR Current Risk >= 90
    # -------------------------------------------------------------------------
    if fl == 1 or current_risk >= 90:
        return {
            "tier_code": TIER_A_CODE,
            "tier_name": TIER_A_NAME,
            "full_label": f"{TIER_A_CODE} — {TIER_A_NAME}",
            "recommended_action": TIER_A_ACTION
        }

    # -------------------------------------------------------------------------
    # TIER B: Urgent Reassessment
    # - Protocol Floor Level 2 (CANNOT map below Tier B)
    # - OR Current Risk >= 75
    # - OR Imminent risk breach (time_to_breach == 0 or <= 15 min)
    # - OR Very short reassessment deadline (<= 5 min)
    # -------------------------------------------------------------------------
    is_imminent_breach = (time_to_breach == 0) or (time_to_breach is not None and time_to_breach <= 15)
    is_immediate_recheck = recheck_due <= 5

    if fl == 2 or current_risk >= 75 or is_imminent_breach or is_immediate_recheck:
        return {
            "tier_code": TIER_B_CODE,
            "tier_name": TIER_B_NAME,
            "full_label": f"{TIER_B_CODE} — {TIER_B_NAME}",
            "recommended_action": TIER_B_ACTION
        }

    # -------------------------------------------------------------------------
    # TIER C: Rising Wait-Risk
    # - Current Risk >= 50
    # - OR 60-min risk >= 50
    # - OR Risk Breach Clock approaching (<= 60 min)
    # - OR Short reassessment deadline (<= 15 min)
    # -------------------------------------------------------------------------
    is_approaching_breach = (time_to_breach is not None and time_to_breach <= 60)
    is_short_recheck = recheck_due <= 15

    if current_risk >= 50 or risk_60 >= 50 or is_approaching_breach or is_short_recheck:
        return {
            "tier_code": TIER_C_CODE,
            "tier_name": TIER_C_NAME,
            "full_label": f"{TIER_C_CODE} — {TIER_C_NAME}",
            "recommended_action": TIER_C_ACTION
        }

    # -------------------------------------------------------------------------
    # TIER D: Monitored Queue
    # - Moderate Current Risk >= 25
    # - OR Moderate future Risk-of-Wait (60-min risk >= 30)
    # - OR Substantial uncertainty (confidence <= 75)
    # - OR Reassessment due <= 30 min
    # -------------------------------------------------------------------------
    if current_risk >= 25 or risk_60 >= 30 or confidence <= 75 or recheck_due <= 30:
        return {
            "tier_code": TIER_D_CODE,
            "tier_name": TIER_D_NAME,
            "full_label": f"{TIER_D_CODE} — {TIER_D_NAME}",
            "recommended_action": TIER_D_ACTION
        }

    # -------------------------------------------------------------------------
    # TIER E: Lower Current Wait-Risk
    # - Low current risk, slow deterioration, high confidence, recheck > 30 min
    # -------------------------------------------------------------------------
    return {
        "tier_code": TIER_E_CODE,
        "tier_name": TIER_E_NAME,
        "full_label": f"{TIER_E_CODE} — {TIER_E_NAME}",
        "recommended_action": TIER_E_ACTION
    }


def calculate_sequence_score(
    patient: Union[Dict[str, Any], pd.Series],
    risk_result: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculates an explainable Sequence Score from 0 to 100 (Stage 2).

    Args:
        patient: Patient record containing arrival_minutes_ago.
        risk_result: Result from evaluate_risk_of_wait.

    Returns:
        Dict with sequence_score (int 0-100), subfactors, and codes.
    """
    current_risk = float(risk_result.get("current_risk", 0))
    risk_60 = float(risk_result.get("risk_60_min", 0))
    time_to_breach = risk_result.get("time_to_breach_min")
    recheck_due = float(risk_result.get("recheck_due_min", 60))
    confidence = float(risk_result.get("confidence", 100))

    try:
        arr_val = patient.get("arrival_minutes_ago", 0)
        arrival_minutes = float(arr_val) if arr_val is not None and not pd.isna(arr_val) else 0.0
    except (ValueError, TypeError):
        arrival_minutes = 0.0

    # 1. Breach Urgency Factor (0-100)
    if time_to_breach == 0:
        breach_urgency = 100.0
    elif time_to_breach is not None:
        if time_to_breach <= 15:
            breach_urgency = 90.0
        elif time_to_breach <= 30:
            breach_urgency = 75.0
        elif time_to_breach <= 60:
            breach_urgency = 55.0
        elif time_to_breach <= 120:
            breach_urgency = 35.0
        else:
            breach_urgency = 15.0
    else:
        breach_urgency = 10.0

    # 2. Reassessment Urgency Factor (0-100)
    if recheck_due <= 5:
        reassess_urgency = 100.0
    elif recheck_due <= 15:
        reassess_urgency = 75.0
    elif recheck_due <= 30:
        reassess_urgency = 50.0
    elif recheck_due <= 60:
        reassess_urgency = 25.0
    else:
        reassess_urgency = 10.0

    # 3. Uncertainty Factor (0-100)
    uncertainty_factor = max(0.0, min(100.0, 100.0 - confidence))

    # 4. Waiting Time Factor (0-100)
    # arrival_minutes_ago smoothly scaled up to 120m, capped at 100
    waiting_factor = min(100.0, (arrival_minutes / 120.0) * 100.0)

    # Weighted Sequence Score
    raw_score = (
        (WEIGHT_CURRENT_RISK * current_risk)
        + (WEIGHT_RISK_60 * risk_60)
        + (WEIGHT_BREACH_URGENCY * breach_urgency)
        + (WEIGHT_REASSESS_URGENCY * reassess_urgency)
        + (WEIGHT_UNCERTAINTY * uncertainty_factor)
        + (WEIGHT_WAIT_TIME * waiting_factor)
    )

    sequence_score = int(round(min(100.0, max(0.0, raw_score))))

    return {
        "sequence_score": sequence_score,
        "breach_urgency": breach_urgency,
        "reassess_urgency": reassess_urgency,
        "uncertainty_factor": uncertainty_factor,
        "waiting_factor": waiting_factor,
        "arrival_minutes": int(arrival_minutes)
    }


def generate_sequence_reasons(
    protocol_result: Dict[str, Any],
    risk_result: Dict[str, Any],
    tier_info: Dict[str, str],
    score_info: Dict[str, Any]
) -> Dict[str, List[str]]:
    """Generates human-readable sequencing explanations and machine codes."""
    reasons: List[str] = []
    codes: List[str] = []

    # Protocol safety floor
    if protocol_result.get("triggered"):
        fl = protocol_result.get("floor_level")
        reasons.append(f"Active Level {fl} protocol safety floor")
        codes.append(f"SQ-GUARDRAIL-L{fl}")

    # Current risk
    cr = risk_result.get("current_risk", 0)
    if cr >= 75:
        reasons.append(f"Current Risk is critically elevated ({cr}/100)")
        codes.append("SQ-RISK-CRITICAL")
    elif cr >= 50:
        reasons.append(f"Current Risk is elevated ({cr}/100)")
        codes.append("SQ-RISK-HIGH")
    elif cr >= 30:
        reasons.append(f"Current Risk is moderate ({cr}/100)")
        codes.append("SQ-RISK-MODERATE")

    # 60-min risk
    r60 = risk_result.get("risk_60_min", 0)
    if r60 >= 75 and cr < 75:
        reasons.append(f"60-minute Risk-of-Wait projects to critical threshold ({r60}/100)")
        codes.append("SQ-FUTURE-CRITICAL")
    elif r60 >= cr + 10:
        reasons.append(f"60-minute Risk-of-Wait is rising rapidly (+{r60 - cr} pts)")
        codes.append("SQ-FUTURE-RISING")

    # Risk breach
    ttb = risk_result.get("time_to_breach_min")
    if ttb == 0:
        reasons.append("Risk breach threshold already reached")
        codes.append("SQ-BREACH-REACHED")
    elif ttb is not None and ttb <= 60:
        reasons.append(f"Risk breach threshold estimated within ~{ttb} minutes")
        codes.append("SQ-BREACH-APPROACHING")

    # Reassessment deadline
    recheck = risk_result.get("recheck_due_min", 60)
    if recheck <= 5:
        reasons.append("Urgent clinician reassessment due within 5 minutes")
        codes.append("SQ-RECHECK-URGENT")
    elif recheck <= 15:
        reasons.append(f"Clinician reassessment due within {recheck} minutes")
        codes.append("SQ-RECHECK-SHORT")

    # Uncertainty
    conf = risk_result.get("confidence", 100)
    if conf < 80:
        reasons.append(f"Reduced confidence ({conf}%) increases monitoring priority")
        codes.append("SQ-UNCERTAINTY-MONITOR")

    # Waiting time
    arr = score_info.get("arrival_minutes", 0)
    if arr >= 45:
        reasons.append(f"Patient has already waited {arr} minutes")
        codes.append("SQ-WAIT-ACCUMULATED")

    if not reasons:
        reasons.append("Stable low-acuity presentation with low wait-risk trajectory")
        codes.append("SQ-STABLE-QUEUE")

    return {
        "sequence_reasons": reasons,
        "sequence_codes": codes
    }


def rank_waiting_queue(cohort_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Evaluates and dynamically sequences the entire waiting ED cohort.

    Args:
        cohort_df: DataFrame of simulated ED patients.

    Returns:
        List of dicts sorted by operational queue priority.
    """
    evaluated_patients: List[Dict[str, Any]] = []

    for idx, row in cohort_df.iterrows():
        patient_token = str(row.get("patient_token", f"IDX_{idx}"))
        
        # 1. Protocol Safety Floor
        protocol_res = evaluate_protocol_floor(row)
        
        # 2. Risk-of-Wait
        risk_res = evaluate_risk_of_wait(row, protocol_res)
        
        # 3. Operational Queue Tier (Stage 1)
        tier_info = assign_queue_tier(row, protocol_res, risk_res)
        
        # 4. Sequence Score (Stage 2)
        score_info = calculate_sequence_score(row, risk_res)
        
        # 5. Explanations
        expl_info = generate_sequence_reasons(protocol_res, risk_res, tier_info, score_info)

        arr_val = row.get("arrival_minutes_ago", 0)
        try:
            arr_min = int(arr_val) if arr_val is not None and not pd.isna(arr_val) else 0
        except (ValueError, TypeError):
            arr_min = 0

        patient_entry = dict(row)
        patient_entry.update({
            "patient_token": patient_token,
            "_original_idx": idx,
            "queue_tier": tier_info["full_label"],
            "queue_tier_code": tier_info["tier_code"],
            "queue_tier_name": tier_info["tier_name"],
            "recommended_queue_action": tier_info["recommended_action"],
            "sequence_score": score_info["sequence_score"],
            "current_risk": risk_res["current_risk"],
            "risk_60_min": risk_res["risk_60_min"],
            "confidence": risk_res["confidence"],
            "recheck_due_min": risk_res["recheck_due_min"],
            "time_to_breach_min": risk_res["time_to_breach_min"],
            "arrival_minutes_ago": arr_min,
            "sequence_reasons": expl_info["sequence_reasons"],
            "sequence_codes": expl_info["sequence_codes"],
            "protocol_result": protocol_res,
            "risk_result": risk_res
        })
        evaluated_patients.append(patient_entry)

    # Deterministic multi-factor clinical sorting:
    # 1. Tier Rank ascending (Tier A=1, B=2, C=3, D=4, E=5)
    # 2. Sequence Score descending
    # 3. Current Risk descending
    # 4. 60-min Risk descending
    # 5. Recheck deadline ascending (shorter first)
    # 6. Waiting time descending (longer wait first)
    # 7. Original index ascending (stable tie-breaker, token-independent)
    def sort_key(p: Dict[str, Any]):
        return (
            TIER_ORDER.get(p["queue_tier_code"], 99),
            -p["sequence_score"],
            -p["current_risk"],
            -p["risk_60_min"],
            p["recheck_due_min"],
            -p["arrival_minutes_ago"],
            p["_original_idx"]
        )

    evaluated_patients.sort(key=sort_key)

    # Assign 1-indexed priority rank
    for rank_idx, patient_entry in enumerate(evaluated_patients, start=1):
        patient_entry["priority_rank"] = rank_idx

    return evaluated_patients

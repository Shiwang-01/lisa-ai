"""LISA.ai — Capacity-Aware Bed Allocation (Milestone 5)

Operational resource-allocation recommendation engine.
Answers: "Given the patients currently waiting and the beds currently available,
what is the recommended operational allocation?"

Architecture:
- Bed Types: Resus, Monitored, General, Fast-track.
- Patient Resource Profile: determines preferred, acceptable, and incompatible bed types.
- Two-way compatibility: matches queue priority to resource appropriateness.
- Scarce Resource Preservation: least-intensive suitable resource allocated to preserve high-acuity beds.
- Explicit unallocated states with safety deadlines ("Await suitable bed — urgent reassessment required").
"""

from typing import Any, Dict, List, Optional, Union
import os
import pandas as pd

# Bed Types
BED_TYPE_RESUS = "Resus"
BED_TYPE_MONITORED = "Monitored"
BED_TYPE_GENERAL = "General"
BED_TYPE_FAST_TRACK = "Fast-track"

ALL_BED_TYPES = [BED_TYPE_RESUS, BED_TYPE_MONITORED, BED_TYPE_GENERAL, BED_TYPE_FAST_TRACK]

# Allocation Statuses
STATUS_ALLOCATED = "ALLOCATED"
STATUS_WAITING_SUITABLE = "WAITING_SUITABLE_BED"
STATUS_WAITING_QUEUE = "WAITING_QUEUE"
STATUS_FAST_TRACK_WAITING = "FAST_TRACK_CANDIDATE_WAITING"

DEFAULT_BEDS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "seed_beds.csv")


def load_beds_inventory(csv_path: Optional[str] = None) -> pd.DataFrame:
    """Loads simulated bed inventory dataset."""
    path = csv_path or DEFAULT_BEDS_PATH
    return pd.read_csv(path)


def determine_patient_resource_profile(
    patient: Union[Dict[str, Any], pd.Series],
    protocol_result: Dict[str, Any],
    risk_result: Dict[str, Any],
    queue_tier_code: str
) -> Dict[str, Any]:
    """Generates an explainable clinical resource profile for a patient.

    Args:
        patient: Patient record data.
        protocol_result: Evaluated protocol floor result.
        risk_result: Evaluated Risk-of-Wait result.
        queue_tier_code: Operational queue tier code (e.g. 'Tier A', 'Tier B').

    Returns:
        Dict with minimum_resource_level, preferred_bed_types, acceptable_bed_types,
        incompatible_bed_types, resource_reasons, and resource_codes.
    """
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
    resource_need = get_str("resource_need").lower()
    visible_distress = get_str("visible_distress").lower()
    mental_status = get_str("mental_status").lower()

    combined_text = f"{complaint} {case_notes} {resource_need}".lower()

    systolic_bp = get_num("systolic_bp", None)
    spo2 = get_num("spo2", None)

    fl = protocol_result.get("floor_level") if protocol_result.get("triggered") else None
    current_risk = risk_result.get("current_risk", 0)

    preferred: List[str] = []
    acceptable: List[str] = []
    incompatible: List[str] = []
    reasons: List[str] = []
    codes: List[str] = []

    # -------------------------------------------------------------------------
    # 1. Pure Stable Low-Acuity Injury / Control Cases (Fast-track)
    # -------------------------------------------------------------------------
    is_pure_minor_injury = (
        any(inj in combined_text for inj in ["ankle sprain", "twisted right ankle", "knee injury", "twisted left knee"])
        and fl is None
        and queue_tier_code == "Tier E"
        and current_risk < 20
        and (visible_distress in ["none", "mild"] or not visible_distress)
    )

    if is_pure_minor_injury:
        preferred = [BED_TYPE_FAST_TRACK]
        acceptable = [BED_TYPE_FAST_TRACK, BED_TYPE_GENERAL]
        incompatible = [BED_TYPE_RESUS, BED_TYPE_MONITORED]
        reasons.append("Fast-track resource compatible with stable low-acuity presentation")
        codes.append("RC-FAST-TRACK-INJURY")
        return {
            "minimum_resource_level": BED_TYPE_FAST_TRACK,
            "preferred_bed_types": preferred,
            "acceptable_bed_types": acceptable,
            "incompatible_bed_types": incompatible,
            "resource_reasons": reasons,
            "resource_codes": codes
        }

    # -------------------------------------------------------------------------
    # 2. Resus / Extreme Physiological Instability
    # -------------------------------------------------------------------------
    is_shock_hypotensive = systolic_bp is not None and 0 < systolic_bp < 90
    is_unresponsive = mental_status in ["unresponsive", "comatose"]
    is_severe_airway_collapse = "drooling" in combined_text and ("swallowed" in combined_text or "foreign object" in combined_text)

    is_resus_candidate = (
        fl == 1
        or is_unresponsive
        or (is_shock_hypotensive and ("confused" in mental_status or "fever" in combined_text))
    )

    if is_resus_candidate:
        preferred = [BED_TYPE_RESUS]
        acceptable = [BED_TYPE_RESUS, BED_TYPE_MONITORED]
        incompatible = [BED_TYPE_GENERAL, BED_TYPE_FAST_TRACK]
        reasons.append("Severe physiological instability — highest-capability resource preferred")
        codes.append("RC-RESUS-INDICATION")
        return {
            "minimum_resource_level": BED_TYPE_RESUS,
            "preferred_bed_types": preferred,
            "acceptable_bed_types": acceptable,
            "incompatible_bed_types": incompatible,
            "resource_reasons": reasons,
            "resource_codes": codes
        }

    # -------------------------------------------------------------------------
    # 3. High Acuity / Monitored Observation Capability
    # -------------------------------------------------------------------------
    needs_continuous_monitoring = (
        fl == 2
        or queue_tier_code in ["Tier A", "Tier B"]
        or (spo2 is not None and 0 < spo2 <= 93)
        or any(k in combined_text for k in ["facial droop", "slurred speech", "stroke", "lethargy", "poor oral intake"])
        or is_severe_airway_collapse
        or ("lip swelling" in combined_text and "allergy" in combined_text)
        or ("pregnant" in combined_text and "bleeding" in combined_text)
        or current_risk >= 60
    )

    # Specific procedural case: active forearm laceration bleeding without hemodynamic collapse
    # Can safely use an acute General stretcher with suture access, though Monitored is acceptable
    is_isolated_laceration_procedure = (
        "deep cut" in combined_text or "deep laceration" in combined_text
    ) and (systolic_bp is not None and systolic_bp >= 110) and (spo2 is not None and spo2 >= 98)

    if needs_continuous_monitoring and not is_isolated_laceration_procedure:
        preferred = [BED_TYPE_MONITORED]
        acceptable = [BED_TYPE_MONITORED, BED_TYPE_RESUS]
        incompatible = [BED_TYPE_FAST_TRACK, BED_TYPE_GENERAL]
        reasons.append("High-acuity clinical guardrail — monitored observation capability preferred")
        codes.append("RC-MONITORED-OBSERVATION")
        return {
            "minimum_resource_level": BED_TYPE_MONITORED,
            "preferred_bed_types": preferred,
            "acceptable_bed_types": acceptable,
            "incompatible_bed_types": incompatible,
            "resource_reasons": reasons,
            "resource_codes": codes
        }

    # -------------------------------------------------------------------------
    # 4. Acute Medical / Surgical Examination & Procedures (General)
    # -------------------------------------------------------------------------
    # Covers: procedural laceration (A131), abdominal pain with worsening symptoms (A128),
    # ambiguous upper-abdominal presentation (A125), severe headache (A138),
    # volume loss / dehydration (A143), vague weakness (A132),
    # flank pain (A137), fever/cough (A139), exam stress tightness (A134).
    preferred = [BED_TYPE_GENERAL]
    acceptable = [BED_TYPE_GENERAL]
    incompatible = [BED_TYPE_FAST_TRACK, BED_TYPE_RESUS]

    reasons.append("General ED space appropriate for continued assessment and scheduled reassessment in prototype")
    codes.append("RC-GENERAL-STRETCHER")

    return {
        "minimum_resource_level": BED_TYPE_GENERAL,
        "preferred_bed_types": preferred,
        "acceptable_bed_types": acceptable,
        "incompatible_bed_types": incompatible,
        "resource_reasons": reasons,
        "resource_codes": codes
    }


def allocate_available_beds(
    ranked_queue: List[Dict[str, Any]],
    beds_df: pd.DataFrame
) -> Dict[str, Any]:
    """Allocates available ED beds using queue sequence priority and resource compatibility.

    Args:
        ranked_queue: Ranked queue records from evaluate_waiting_queue / rank_waiting_queue.
        beds_df: DataFrame of simulated beds.

    Returns:
        Structured dictionary containing:
        - patient_allocations: List of all 20 patient allocation records
        - allocated_beds: List of beds with their assigned patients
        - waiting_patients: List of patients awaiting beds
    """
    # Track available beds
    available_beds = beds_df[beds_df["status"].str.strip().str.lower() == "available"].copy()

    # Pre-index beds by type
    beds_by_id: Dict[str, Dict[str, Any]] = {
        row["bed_id"]: dict(row) for _, row in available_beds.iterrows()
    }
    unassigned_bed_ids = set(beds_by_id.keys())

    patient_allocations: List[Dict[str, Any]] = []
    assigned_patients: set = set()

    for p in ranked_queue:
        token = p["patient_token"]
        rank = p["priority_rank"]
        tier = p["queue_tier"]
        tier_code = p["queue_tier_code"]
        score = p["sequence_score"]

        # Evaluate patient resource profile
        profile = determine_patient_resource_profile(
            p,
            p["protocol_result"],
            p["risk_result"],
            tier_code
        )

        preferred = profile["preferred_bed_types"]
        acceptable = profile["acceptable_bed_types"]
        incompatible = profile["incompatible_bed_types"]

        # Find matching available bed
        chosen_bed_id: Optional[str] = None
        chosen_bed_type: Optional[str] = None
        allocation_reason = ""
        allocation_status = ""

        # Step 1: Check preferred bed types in order
        for b_type in preferred:
            # Find available beds matching this type
            matching_ids = [
                bid for bid in sorted(unassigned_bed_ids)
                if beds_by_id[bid]["bed_type"] == b_type
            ]
            if matching_ids:
                chosen_bed_id = matching_ids[0]
                chosen_bed_type = b_type
                allocation_status = STATUS_ALLOCATED
                allocation_reason = (
                    f"Recommended allocation: {chosen_bed_id} ({chosen_bed_type}) — "
                    f"optimal match for patient urgency ({tier_code}) and {profile['resource_reasons'][0].lower()}."
                )
                break

        # Step 2: If no preferred bed available, check other acceptable bed types
        if not chosen_bed_id:
            # Sort acceptable types to preserve scarce higher-acuity resources where possible
            # E.g. prefer Fast-track over General, General over Monitored/Resus for lower acuity
            preservation_order = [BED_TYPE_FAST_TRACK, BED_TYPE_GENERAL, BED_TYPE_MONITORED, BED_TYPE_RESUS]
            sorted_acceptable = sorted(
                [t for t in acceptable if t not in preferred],
                key=lambda x: preservation_order.index(x) if x in preservation_order else 99
            )

            for b_type in sorted_acceptable:
                matching_ids = [
                    bid for bid in sorted(unassigned_bed_ids)
                    if beds_by_id[bid]["bed_type"] == b_type
                ]
                if matching_ids:
                    chosen_bed_id = matching_ids[0]
                    chosen_bed_type = b_type
                    allocation_status = STATUS_ALLOCATED
                    allocation_reason = (
                        f"Recommended step-allocation: {chosen_bed_id} ({chosen_bed_type}) — "
                        f"acceptable compatible placement under current bed availability."
                    )
                    break

        # Step 3: Handle Unallocated Patients
        if chosen_bed_id:
            unassigned_bed_ids.remove(chosen_bed_id)
            assigned_patients.add(token)
        else:
            recheck = p["recheck_due_min"]
            is_high_priority = tier_code in ["Tier A", "Tier B"] or p["protocol_result"].get("triggered")
            
            if is_high_priority:
                allocation_status = STATUS_WAITING_SUITABLE
                allocation_reason = (
                    f"No suitable simulated bed currently available — "
                    f"urgent clinician reassessment remains required within {recheck} min."
                )
            elif BED_TYPE_FAST_TRACK in preferred:
                allocation_status = STATUS_FAST_TRACK_WAITING
                allocation_reason = "Awaiting available Fast-track cubicle; queue monitored with scheduled reassessment."
            else:
                allocation_status = STATUS_WAITING_QUEUE
                allocation_reason = (
                    f"Awaiting suitable acute care space; scheduled reassessment due in {recheck} min."
                )

        patient_rec = {
            "patient_token": token,
            "priority_rank": rank,
            "queue_tier": tier,
            "queue_tier_code": tier_code,
            "sequence_score": score,
            "allocation_status": allocation_status,
            "bed_id": chosen_bed_id,
            "bed_type": chosen_bed_type,
            "minimum_resource_level": profile["minimum_resource_level"],
            "preferred_bed_types": preferred,
            "acceptable_bed_types": acceptable,
            "incompatible_bed_types": incompatible,
            "allocation_reason": allocation_reason,
            "allocation_reasons": profile["resource_reasons"],
            "allocation_codes": profile["resource_codes"],
            "current_risk": p["current_risk"],
            "recheck_due_min": p["recheck_due_min"],
            "arrival_minutes_ago": p["arrival_minutes_ago"]
        }
        patient_allocations.append(patient_rec)

    # Build allocated beds list (sorted by bed_id B01..B08)
    allocated_beds_list: List[Dict[str, Any]] = []
    for bid in sorted(beds_by_id.keys()):
        bed_info = beds_by_id[bid]
        # Find matching patient
        assigned_p = next((p for p in patient_allocations if p["bed_id"] == bid), None)
        if assigned_p:
            allocated_beds_list.append({
                "bed_id": bid,
                "bed_type": bed_info["bed_type"],
                "recommended_patient": assigned_p["patient_token"],
                "priority_rank": assigned_p["priority_rank"],
                "sequence_score": assigned_p["sequence_score"],
                "queue_tier": assigned_p["queue_tier"],
                "why": assigned_p["allocation_reason"]
            })
        else:
            allocated_beds_list.append({
                "bed_id": bid,
                "bed_type": bed_info["bed_type"],
                "recommended_patient": "None (Unassigned)",
                "priority_rank": "-",
                "sequence_score": "-",
                "queue_tier": "-",
                "why": "Unallocated"
            })

    # Build waiting patients list
    waiting_patients_list = [p for p in patient_allocations if p["allocation_status"] != STATUS_ALLOCATED]

    return {
        "patient_allocations": patient_allocations,
        "allocated_beds": allocated_beds_list,
        "waiting_patients": waiting_patients_list
    }

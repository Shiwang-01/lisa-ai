"""LISA.ai — Nurse Command Center FastAPI Backend (Milestone 11A)

Thin FastAPI adapter over existing deterministic LISA Python engines.
Provides JSON REST API for ED queue sequencing, patient inspector,
resource allocation, surge modeling, policy comparisons, and clinician audit logs.

Maintains existing clinical/operational Python modules as the single source of truth.
"""

from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import pandas as pd

from lisa.protocol_floor import evaluate_protocol_floor
from lisa.risk_engine import evaluate_risk_of_wait
from lisa.sequencer import rank_waiting_queue
from lisa.allocator import allocate_available_beds, STATUS_ALLOCATED
from lisa.surge_simulator import (
    get_operational_mode,
    compute_surge_summary,
    MODE_NORMAL,
    MODE_SURGE_3X,
)
from lisa.comparison_metrics import compare_queue_policies
from lisa.audit_log import (
    AuditTrailManager,
    create_audit_event,
    validate_clinician_override,
    calculate_escalated_tier,
    ACTION_ACCEPT,
    ACTION_OVERRIDE,
    ACTION_ESCALATE,
    OVERRIDE_REASONS,
    DEFAULT_USER_ROLE,
)
from lisa.governance import get_governance_summary

app = FastAPI(
    title="LISA.ai Backend API",
    description="Deterministic Emergency Department Sequencing & Capacity-Aware Decision Support API",
    version="1.0.0",
)

# Enable CORS for local web development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Process-scoped session audit manager
audit_manager = AuditTrailManager()


# =============================================================================
# HELPERS
# =============================================================================

def normalize_mode(mode: Optional[str]) -> str:
    """Validates and normalizes operational mode input."""
    if not mode:
        return MODE_NORMAL
    m = mode.strip().upper()
    if m in ["NORMAL", "MODE_NORMAL"]:
        return MODE_NORMAL
    elif m in ["SURGE", "SURGE_3X", "MODE_SURGE_3X"]:
        return MODE_SURGE_3X
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid mode '{mode}'. Supported modes: NORMAL, SURGE_3X",
        )


def get_mode_pipeline_data(mode_code: str) -> Dict[str, Any]:
    """Executes the deterministic LISA pipeline for the requested mode."""
    mode_context = get_operational_mode(mode_code)
    patients_df = mode_context["patients"]
    beds_df = mode_context["beds_df"]

    ranked_queue = rank_waiting_queue(patients_df)
    allocation_results = allocate_available_beds(ranked_queue, beds_df)
    surge_summary = compute_surge_summary(
        ranked_queue, allocation_results, len(beds_df), mode_code
    )

    return {
        "mode_code": mode_code,
        "patients_df": patients_df,
        "beds_df": beds_df,
        "ranked_queue": ranked_queue,
        "allocation_results": allocation_results,
        "surge_summary": surge_summary,
    }


def safe_val(val: Any, default: Any = None) -> Any:
    """Sanitizes NaN and missing pandas values for clean JSON output."""
    if pd.isna(val) or val is None:
        return default
    return val


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class ActionBaseRequest(BaseModel):
    patient_token: str
    mode: str = "NORMAL"
    user_role: str = DEFAULT_USER_ROLE


class OverrideRequest(ActionBaseRequest):
    target_tier: str
    reason: str
    note: Optional[str] = None


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.get("/api/status")
def get_status() -> Dict[str, Any]:
    """Returns application status and prototype disclaimer."""
    return {
        "application": "LISA.ai",
        "status": "ok",
        "prototype": True,
        "clinical_use": False,
        "supported_modes": [MODE_NORMAL, MODE_SURGE_3X],
    }


@app.get("/api/summary")
def get_summary(mode: str = Query("NORMAL")) -> Dict[str, Any]:
    """Returns operational pressure summary and capacity metrics for the selected mode."""
    mode_code = normalize_mode(mode)
    data = get_mode_pipeline_data(mode_code)
    s = data["surge_summary"]

    patients_df = data["patients_df"]
    avg_wait = (
        float(patients_df["arrival_minutes_ago"].mean())
        if "arrival_minutes_ago" in patients_df.columns
        else 0.0
    )

    return {
        "mode": mode_code,
        "patient_count": int(s["patient_count"]),
        "bed_count": int(s.get("available_bed_count", 8)),
        "patients_per_bed": float(s["patients_per_bed"]),
        "patients_per_triage_nurse": float(s["patients_per_triage_nurse"]),
        "tier_a_count": int(s["tier_a_count"]),
        "tier_b_count": int(s["tier_b_count"]),
        "tier_c_count": int(s["tier_c_count"]),
        "tier_d_count": int(s["tier_d_count"]),
        "tier_e_count": int(s["tier_e_count"]),
        "reassess_within_5_min": int(s["reassess_within_5_min"]),
        "reassess_within_15_min": int(s["reassess_within_15_min"]),
        "reassess_within_30_min": int(s["reassess_within_30_min"]),
        "hard_protocol_floor_count": int(s["hard_protocol_floor_count"]),
        "allocated_count": int(s["allocated_count"]),
        "waiting_suitable_bed_count": int(s["waiting_suitable_bed_count"]),
        "waiting_queue_count": int(s["waiting_queue_count"]),
        "avg_wait_min": round(avg_wait, 1),
    }


@app.get("/api/queue")
def get_queue(mode: str = Query("NORMAL")) -> List[Dict[str, Any]]:
    """Returns the sequenced queue list with workstation-relevant fields."""
    mode_code = normalize_mode(mode)
    data = get_mode_pipeline_data(mode_code)
    ranked = data["ranked_queue"]
    alloc_map = {
        p["patient_token"]: p
        for p in data["allocation_results"]["patient_allocations"]
    }

    queue_list = []
    for p in ranked:
        token = p["patient_token"]
        alloc = alloc_map.get(token, {})

        queue_list.append({
            "patient_token": token,
            "priority_rank": p["priority_rank"],
            "queue_tier": p["queue_tier"],
            "queue_tier_code": p["queue_tier_code"],
            "sequence_score": p["sequence_score"],
            "age": int(p["age"]),
            "sex": str(p["sex"]),
            "complaint_text": str(p["complaint_text"]),
            "arrival_minutes_ago": int(p["arrival_minutes_ago"]),
            "current_risk": int(p["current_risk"]),
            "risk_60_min": int(p["risk_60_min"]),
            "confidence": int(p["confidence"]),
            "recheck_due_min": int(p["recheck_due_min"]),
            "initial_triage_level": (
                int(p["initial_triage_level"])
                if pd.notna(p.get("initial_triage_level"))
                else None
            ),
            "protocol_floor_level": p.get("protocol_floor_level"),
            "effective_safety_floor": p.get("effective_safety_floor"),
            "effective_safety_floor_source": p.get("effective_safety_floor_source"),
            "recommended_queue_action": p.get("recommended_queue_action"),
            "sequence_reasons": p.get("sequence_reasons", []),
            "allocation_status": alloc.get("allocation_status"),
            "target_bed_id": alloc.get("bed_id"),
            "target_bed_type": alloc.get("bed_type"),
        })

    return queue_list


@app.get("/api/patient/{patient_token}")
def get_patient(patient_token: str, mode: str = Query("NORMAL")) -> Dict[str, Any]:
    """Returns comprehensive patient profile, safety guardrails, Risk-of-Wait trajectory, and allocation details."""
    mode_code = normalize_mode(mode)
    data = get_mode_pipeline_data(mode_code)
    patients_df = data["patients_df"]

    patient_rows = patients_df[patients_df["patient_token"] == patient_token]
    if patient_rows.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with token '{patient_token}' not found in {mode_code} cohort.",
        )
    row = patient_rows.iloc[0]

    f_res = evaluate_protocol_floor(row)
    r_res = evaluate_risk_of_wait(row, f_res)

    ranked_p = next(
        (p for p in data["ranked_queue"] if p["patient_token"] == patient_token),
        None,
    )
    if not ranked_p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient sequencing record not found.",
        )

    alloc_p = next(
        (
            p
            for p in data["allocation_results"]["patient_allocations"]
            if p["patient_token"] == patient_token
        ),
        {},
    )

    latest_action = audit_manager.get_latest_action_for_patient(patient_token)

    return {
        "patient": {
            "patient_token": patient_token,
            "age": int(row["age"]),
            "sex": str(row["sex"]),
            "complaint_text": str(row["complaint_text"]),
            "language": safe_val(row.get("language"), "English"),
            "arrival_minutes_ago": int(row["arrival_minutes_ago"]),
            "heart_rate": (
                int(row["heart_rate"])
                if pd.notna(row.get("heart_rate"))
                else None
            ),
            "respiratory_rate": (
                int(row["respiratory_rate"])
                if pd.notna(row.get("respiratory_rate"))
                else None
            ),
            "systolic_bp": (
                int(row["systolic_bp"])
                if pd.notna(row.get("systolic_bp"))
                else None
            ),
            "diastolic_bp": (
                int(row["diastolic_bp"])
                if pd.notna(row.get("diastolic_bp"))
                else None
            ),
            "spo2": (
                int(row["spo2"]) if pd.notna(row.get("spo2")) else None
            ),
            "temperature": (
                float(row["temperature"])
                if pd.notna(row.get("temperature"))
                else None
            ),
            "mental_status": safe_val(row.get("mental_status")),
            "visible_distress": safe_val(row.get("visible_distress")),
            "known_history": safe_val(row.get("known_history")),
            "prior_record_available": bool(row.get("prior_record_available", False)),
            "pregnancy_status": safe_val(row.get("pregnancy_status")),
            "initial_triage_level": (
                int(row["initial_triage_level"])
                if pd.notna(row.get("initial_triage_level"))
                else None
            ),
        },
        "guardrails": {
            "triggered": bool(f_res["triggered"]),
            "floor_level": f_res.get("floor_level"),
            "rule_ids": f_res.get("rule_ids", []),
            "reasons": f_res.get("reasons", []),
            "initial_triage_level": ranked_p.get("initial_triage_level"),
            "protocol_floor_level": ranked_p.get("protocol_floor_level"),
            "effective_safety_floor": ranked_p.get("effective_safety_floor"),
            "effective_safety_floor_source": ranked_p.get(
                "effective_safety_floor_source"
            ),
            "has_hard_floor": ranked_p.get("effective_safety_floor") in [1, 2],
        },
        "risk_of_wait": {
            "current_risk": r_res["current_risk"],
            "risk_30_min": r_res["risk_30_min"],
            "risk_60_min": r_res["risk_60_min"],
            "risk_120_min": r_res["risk_120_min"],
            "confidence": r_res["confidence"],
            "risk_band": r_res["risk_band"],
            "time_to_breach_min": r_res.get("time_to_breach_min"),
            "recheck_due_min": r_res["recheck_due_min"],
            "risk_factors": r_res.get("risk_factors", []),
            "uncertainty_factors": r_res.get("uncertainty_factors", []),
            "explanation_codes": r_res.get("explanation_codes", []),
        },
        "queue": {
            "priority_rank": ranked_p["priority_rank"],
            "queue_tier": ranked_p["queue_tier"],
            "queue_tier_code": ranked_p["queue_tier_code"],
            "queue_tier_name": ranked_p.get(
                "queue_tier_name", ranked_p["queue_tier"]
            ),
            "sequence_score": ranked_p["sequence_score"],
            "recommended_queue_action": ranked_p.get("recommended_queue_action"),
            "sequence_reasons": ranked_p.get("sequence_reasons", []),
        },
        "resource": {
            "allocation_status": alloc_p.get("allocation_status"),
            "bed_id": alloc_p.get("bed_id"),
            "bed_type": alloc_p.get("bed_type"),
            "preferred_bed_types": alloc_p.get("preferred_bed_types", []),
            "acceptable_bed_types": alloc_p.get("acceptable_bed_types", []),
            "allocation_reason": alloc_p.get("allocation_reason"),
            "allocation_reasons": alloc_p.get("allocation_reasons", []),
        },
        "clinician_decision": latest_action,
    }


@app.get("/api/allocation")
def get_allocation(mode: str = Query("NORMAL")) -> Dict[str, Any]:
    """Returns bed board allocation status and awaiting waiting list."""
    mode_code = normalize_mode(mode)
    data = get_mode_pipeline_data(mode_code)
    alloc = data["allocation_results"]

    return {
        "mode": mode_code,
        "beds": alloc["allocated_beds"],
        "allocations": [
            p
            for p in alloc["patient_allocations"]
            if p["allocation_status"] == STATUS_ALLOCATED
        ],
        "waiting_patients": alloc["waiting_patients"],
    }


@app.get("/api/comparison")
def get_comparison(mode: str = Query("NORMAL")) -> Dict[str, Any]:
    """Returns Static vs LISA simulation policy comparison metrics."""
    mode_code = normalize_mode(mode)
    data = get_mode_pipeline_data(mode_code)
    comp_result = compare_queue_policies(data["patients_df"])

    return {
        "simulation_only": True,
        "clinical_efficacy_evidence": False,
        "mode": mode_code,
        "comparison": comp_result,
    }


@app.get("/api/governance")
def get_governance() -> Dict[str, Any]:
    """Returns system safety, governance specification, and prototype controls."""
    return get_governance_summary()


@app.post("/api/actions/accept")
def action_accept(req: ActionBaseRequest) -> Dict[str, Any]:
    """Logs clinician acceptance of the system queue recommendation."""
    mode_code = normalize_mode(req.mode)
    data = get_mode_pipeline_data(mode_code)

    ranked_p = next(
        (p for p in data["ranked_queue"] if p["patient_token"] == req.patient_token),
        None,
    )
    if not ranked_p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{req.patient_token}' not found.",
        )

    alloc_p = next(
        (
            p
            for p in data["allocation_results"]["patient_allocations"]
            if p["patient_token"] == req.patient_token
        ),
        {},
    )

    event = create_audit_event(
        patient_token=req.patient_token,
        action=ACTION_ACCEPT,
        system_ranked_patient=ranked_p,
        system_allocated_patient=alloc_p,
        operational_mode=mode_code,
        user_role=req.user_role,
        clinician_selected_tier=ranked_p["queue_tier_code"],
    )
    audit_manager.log_event(event)

    return {"status": "success", "action": ACTION_ACCEPT, "event": event}


@app.post("/api/actions/escalate")
def action_escalate(req: ActionBaseRequest) -> Dict[str, Any]:
    """Logs one-step upward urgency tier escalation for a patient."""
    mode_code = normalize_mode(req.mode)
    data = get_mode_pipeline_data(mode_code)

    ranked_p = next(
        (p for p in data["ranked_queue"] if p["patient_token"] == req.patient_token),
        None,
    )
    if not ranked_p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{req.patient_token}' not found.",
        )

    alloc_p = next(
        (
            p
            for p in data["allocation_results"]["patient_allocations"]
            if p["patient_token"] == req.patient_token
        ),
        {},
    )

    latest = audit_manager.get_latest_action_for_patient(req.patient_token)
    current_tier = (
        latest["clinician_selected_tier"] if latest else ranked_p["queue_tier_code"]
    )

    event = create_audit_event(
        patient_token=req.patient_token,
        action=ACTION_ESCALATE,
        system_ranked_patient=ranked_p,
        system_allocated_patient=alloc_p,
        operational_mode=mode_code,
        user_role=req.user_role,
        current_active_tier=current_tier,
    )
    audit_manager.log_event(event)

    return {"status": "success", "action": ACTION_ESCALATE, "event": event}


@app.post("/api/actions/override")
def action_override(req: OverrideRequest) -> Dict[str, Any]:
    """Logs clinician override with strict safety-floor validation."""
    mode_code = normalize_mode(req.mode)
    data = get_mode_pipeline_data(mode_code)

    ranked_p = next(
        (p for p in data["ranked_queue"] if p["patient_token"] == req.patient_token),
        None,
    )
    if not ranked_p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{req.patient_token}' not found.",
        )

    alloc_p = next(
        (
            p
            for p in data["allocation_results"]["patient_allocations"]
            if p["patient_token"] == req.patient_token
        ),
        {},
    )

    if req.reason not in OVERRIDE_REASONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid override reason '{req.reason}'. Valid reasons: {OVERRIDE_REASONS}",
        )

    eff_floor = ranked_p.get("effective_safety_floor")
    is_valid, err = validate_clinician_override(eff_floor, req.target_tier, req.reason)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=err,
        )

    try:
        event = create_audit_event(
            patient_token=req.patient_token,
            action=ACTION_OVERRIDE,
            system_ranked_patient=ranked_p,
            system_allocated_patient=alloc_p,
            operational_mode=mode_code,
            user_role=req.user_role,
            clinician_selected_tier=req.target_tier,
            override_reason=req.reason,
            override_note=req.note,
        )
    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(ex),
        )

    audit_manager.log_event(event)

    return {"status": "success", "action": ACTION_OVERRIDE, "event": event}


@app.get("/api/audit")
def get_audit() -> Dict[str, Any]:
    """Returns recorded clinician actions for the current session in reverse chronological order."""
    events = audit_manager.get_events()
    return {
        "count": len(events),
        "events": list(reversed(events)),
    }


@app.post("/api/audit/reset")
def reset_audit() -> Dict[str, Any]:
    """Clears session-scoped clinician action audit logs."""
    audit_manager.clear()
    return {"status": "reset", "message": "Audit trail cleared."}

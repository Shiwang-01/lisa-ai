"""LISA.ai — Comparison Metrics & Policy Evaluation Engine (Milestone 6B)

Simulates operational attention-capacity constraints (1 triage nurse, 5-min slots, 120-min horizon)
and compares:
  Policy A: Static Baseline (Initial Triage + FIFO)
  Policy B: LISA Dynamic Sequencing (Guardrails + Risk-of-Wait + Recheck Urgency + Uncertainty)

All metrics are simulated operational measurements, NOT clinical efficacy evidence.
"""

from typing import Any, Dict, List, Optional
import pandas as pd
import statistics

from lisa.protocol_floor import evaluate_protocol_floor
from lisa.risk_engine import evaluate_risk_of_wait
from lisa.sequencer import rank_waiting_queue
from lisa.baseline_simulator import rank_static_baseline_queue

# Configurable Simulation Constants
SIMULATION_HORIZON_MINUTES = 120
ATTENTION_SLOT_MINUTES = 5
TRIAGE_NURSES = 1
AVAILABLE_ATTENTION_SLOTS = SIMULATION_HORIZON_MINUTES // ATTENTION_SLOT_MINUTES  # 24


def evaluate_policy_attention_schedule(
    ranked_queue: List[Dict[str, Any]],
    lisa_patient_map: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Assigns discrete simulated attention slots and evaluates reassessment deadline adherence.

    Args:
        ranked_queue: List of patients sorted by the given policy.
        lisa_patient_map: Pre-evaluated LISA clinical profile map (for shared floor/risk metrics).

    Returns:
        Enriched list of patient records with attention schedule and delay details.
    """
    enriched_list: List[Dict[str, Any]] = []

    for rank, p in enumerate(ranked_queue, start=1):
        token = p["patient_token"]
        lisa_data = lisa_patient_map[token]

        recheck_due = lisa_data["recheck_due_min"]
        queue_tier_code = lisa_data["queue_tier_code"]
        current_risk = lisa_data["current_risk"]
        risk_60_min = lisa_data["risk_60_min"]
        protocol_triggered = lisa_data["protocol_result"].get("triggered", False)
        protocol_floor_level = lisa_data["protocol_result"].get("floor_level")

        # Assign discrete simulated attention time
        if rank <= AVAILABLE_ATTENTION_SLOTS:
            attention_time_min = (rank - 1) * ATTENTION_SLOT_MINUTES
            reviewed_in_horizon = True
        else:
            attention_time_min = None
            reviewed_in_horizon = False

        # Evaluate deadline miss and delay
        if reviewed_in_horizon and attention_time_min is not None:
            if attention_time_min > recheck_due:
                deadline_missed = True
                delay_min = attention_time_min - recheck_due
            else:
                deadline_missed = False
                delay_min = 0
        else:
            # Unreviewed within horizon: if deadline fell within 120 min, it is missed
            if recheck_due <= SIMULATION_HORIZON_MINUTES:
                deadline_missed = True
                delay_min = SIMULATION_HORIZON_MINUTES - recheck_due  # Horizon-censored minimum delay
            else:
                deadline_missed = False
                delay_min = 0

        rec = dict(p)
        rec.update({
            "patient_token": token,
            "policy_rank": rank,
            "scheduled_attention_min": attention_time_min,
            "reviewed_in_horizon": reviewed_in_horizon,
            "recheck_due_min": recheck_due,
            "reassessment_deadline_missed": deadline_missed,
            "delay_minutes": delay_min,
            "queue_tier_code": queue_tier_code,
            "current_risk": current_risk,
            "risk_60_min": risk_60_min,
            "protocol_triggered": protocol_triggered,
            "protocol_floor_level": protocol_floor_level,
        })
        enriched_list.append(rec)

    return enriched_list


def compute_policy_metrics(evaluated_queue: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates operational metrics for an evaluated queue under the attention schedule."""
    total_patients = len(evaluated_queue)

    # 1. Reassessment Deadlines Missed
    missed_patients = [p for p in evaluated_queue if p["reassessment_deadline_missed"]]
    missed_count = len(missed_patients)
    missed_pct = round((missed_count / total_patients) * 100, 1) if total_patients > 0 else 0.0

    # 2. Reassessment Delay (among missed deadlines)
    delays = [p["delay_minutes"] for p in missed_patients]
    if delays:
        avg_delay = round(sum(delays) / len(delays), 1)
        med_delay = round(statistics.median(delays), 1)
    else:
        avg_delay = 0.0
        med_delay = 0.0

    # 3. Urgent Patients (Tier A or B) Reviewed Early (<= 15 min)
    urgent_patients = [p for p in evaluated_queue if p["queue_tier_code"] in ["Tier A", "Tier B"]]
    urgent_total = len(urgent_patients)
    urgent_reviewed_15 = sum(
        1 for p in urgent_patients
        if p["scheduled_attention_min"] is not None and p["scheduled_attention_min"] <= 15
    )
    urgent_reviewed_pct = round((urgent_reviewed_15 / urgent_total) * 100, 1) if urgent_total > 0 else 0.0

    # 4. High Wait-Risk Patients (risk_60_min >= 75) Reviewed Early (<= 30 min)
    high_wait_risk_patients = [p for p in evaluated_queue if p["risk_60_min"] >= 75]
    high_wait_risk_total = len(high_wait_risk_patients)
    high_wait_risk_30 = sum(
        1 for p in high_wait_risk_patients
        if p["scheduled_attention_min"] is not None and p["scheduled_attention_min"] <= 30
    )
    high_wait_risk_pct = (
        round((high_wait_risk_30 / high_wait_risk_total) * 100, 1)
        if high_wait_risk_total > 0 else 0.0
    )

    # 5. Lower-Urgency Displacement (Dynamic-Priority Inversions)
    # Count Tier D / E patients who are ranked before at least one Tier A / B patient
    urgent_ranks = [p["policy_rank"] for p in urgent_patients]
    max_urgent_rank = max(urgent_ranks) if urgent_ranks else 0

    lower_urgency_patients = [p for p in evaluated_queue if p["queue_tier_code"] in ["Tier D", "Tier E"]]
    inversions_count = sum(1 for p in lower_urgency_patients if p["policy_rank"] < max_urgent_rank)

    # 6. Protocol-Floor Timeliness (<= 5 min)
    floor_patients = [p for p in evaluated_queue if p["protocol_triggered"] and p["protocol_floor_level"] in [1, 2]]
    floor_total = len(floor_patients)
    floor_reviewed_5 = sum(
        1 for p in floor_patients
        if p["scheduled_attention_min"] is not None and p["scheduled_attention_min"] <= 5
    )
    floor_reviewed_pct = round((floor_reviewed_5 / floor_total) * 100, 1) if floor_total > 0 else 0.0

    # 7. Coverage (Identical between policies)
    reviewed_in_horizon = min(total_patients, AVAILABLE_ATTENTION_SLOTS)
    not_reviewed_in_horizon = max(0, total_patients - AVAILABLE_ATTENTION_SLOTS)

    return {
        "reassessment_deadlines_missed": missed_count,
        "reassessment_deadlines_missed_pct": missed_pct,
        "average_reassessment_delay_min": avg_delay,
        "median_reassessment_delay_min": med_delay,
        "urgent_reviewed_within_15_min": urgent_reviewed_15,
        "urgent_total": urgent_total,
        "urgent_reviewed_pct": urgent_reviewed_pct,
        "high_wait_risk_reviewed_within_30_min": high_wait_risk_30,
        "high_wait_risk_total": high_wait_risk_total,
        "high_wait_risk_reviewed_pct": high_wait_risk_pct,
        "lower_urgency_ahead_of_urgent_count": inversions_count,
        "protocol_floor_reviewed_within_5_min": floor_reviewed_5,
        "protocol_floor_total": floor_total,
        "protocol_floor_reviewed_pct": floor_reviewed_pct,
        "reviewed_within_horizon": reviewed_in_horizon,
        "not_reviewed_within_horizon": not_reviewed_in_horizon
    }


def compare_queue_policies(cohort_df: pd.DataFrame) -> Dict[str, Any]:
    """Runs a complete deterministic comparison between Static Baseline and LISA policies.

    Args:
        cohort_df: DataFrame of simulated ED patients.

    Returns:
        Structured dictionary containing simulation assumptions, static metrics, LISA metrics,
        operational differences, and merged patient-level results.
    """
    # 1. Run LISA Pipeline to establish common clinical profiles
    lisa_queue = rank_waiting_queue(cohort_df)
    lisa_map = {p["patient_token"]: p for p in lisa_queue}

    # 2. Run Static Baseline Pipeline
    static_queue = rank_static_baseline_queue(cohort_df)

    # 3. Evaluate schedules under limited attention capacity
    lisa_evaluated = evaluate_policy_attention_schedule(lisa_queue, lisa_map)
    static_evaluated = evaluate_policy_attention_schedule(static_queue, lisa_map)

    # 4. Compute Metrics for both policies
    lisa_metrics = compute_policy_metrics(lisa_evaluated)
    static_metrics = compute_policy_metrics(static_evaluated)

    # 5. Compute Absolute Operational Differences
    differences = {
        "reassessment_deadline_breaches_difference": (
            static_metrics["reassessment_deadlines_missed"] - lisa_metrics["reassessment_deadlines_missed"]
        ),
        "average_delay_difference_min": round(
            static_metrics["average_reassessment_delay_min"] - lisa_metrics["average_reassessment_delay_min"], 1
        ),
        "urgent_reviewed_15min_difference": (
            lisa_metrics["urgent_reviewed_within_15_min"] - static_metrics["urgent_reviewed_within_15_min"]
        ),
        "high_wait_risk_reviewed_30min_difference": (
            lisa_metrics["high_wait_risk_reviewed_within_30_min"] - static_metrics["high_wait_risk_reviewed_within_30_min"]
        ),
        "priority_inversion_difference": (
            static_metrics["lower_urgency_ahead_of_urgent_count"] - lisa_metrics["lower_urgency_ahead_of_urgent_count"]
        ),
        "protocol_floor_reviewed_5min_difference": (
            lisa_metrics["protocol_floor_reviewed_within_5_min"] - static_metrics["protocol_floor_reviewed_within_5_min"]
        )
    }

    # 6. Build Patient-Level Merged Comparison Records
    patient_level_results: List[Dict[str, Any]] = []
    static_eval_map = {p["patient_token"]: p for p in static_evaluated}

    for p_lisa in lisa_evaluated:
        token = p_lisa["patient_token"]
        p_static = static_eval_map[token]

        patient_level_results.append({
            "patient_token": token,
            "static_rank": p_static["policy_rank"],
            "lisa_rank": p_lisa["policy_rank"],
            "static_attention_min": p_static["scheduled_attention_min"],
            "lisa_attention_min": p_lisa["scheduled_attention_min"],
            "recheck_due_min": p_lisa["recheck_due_min"],
            "static_deadline_missed": p_static["reassessment_deadline_missed"],
            "lisa_deadline_missed": p_lisa["reassessment_deadline_missed"],
            "static_delay_min": p_static["delay_minutes"],
            "lisa_delay_min": p_lisa["delay_minutes"],
            "queue_tier": p_lisa["queue_tier_code"],
            "60_min_risk": p_lisa["risk_60_min"],
            "current_risk": p_lisa["current_risk"]
        })

    # Sort patient-level results by LISA rank by default
    patient_level_results.sort(key=lambda x: x["lisa_rank"])

    return {
        "simulation_assumptions": {
            "simulation_horizon_min": SIMULATION_HORIZON_MINUTES,
            "attention_slot_min": ATTENTION_SLOT_MINUTES,
            "triage_nurses": TRIAGE_NURSES,
            "available_attention_slots": AVAILABLE_ATTENTION_SLOTS,
            "patient_count": len(cohort_df)
        },
        "static_baseline": static_metrics,
        "lisa": lisa_metrics,
        "differences": differences,
        "patient_level_results": patient_level_results
    }

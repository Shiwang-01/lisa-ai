"""LISA.ai — Surge Mode Simulator (Milestone 6A)

Provides deterministic Normal / Surge 3× operational mode switching.
Surge Mode uses 60 fixed simulated patients competing for the same 8 ED beds.
"""

import os
from typing import Any, Dict, List

import pandas as pd

from lisa.sequencer import rank_waiting_queue
from lisa.allocator import load_beds_inventory, allocate_available_beds, STATUS_ALLOCATED, STATUS_WAITING_SUITABLE

# Operational Mode Constants
MODE_NORMAL = "NORMAL"
MODE_SURGE_3X = "SURGE_3X"

TRIAGE_NURSE_COUNT = 1

NORMAL_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "seed_patients.csv")
SURGE_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "surge_patients.csv")


def load_normal_cohort() -> pd.DataFrame:
    """Loads the standard 20-patient ED cohort."""
    return pd.read_csv(NORMAL_CSV)


def load_surge_cohort() -> pd.DataFrame:
    """Loads the surge 60-patient ED cohort (includes A124-A143 unchanged + A144-A183)."""
    return pd.read_csv(SURGE_CSV)


def get_operational_mode(mode: str) -> Dict[str, Any]:
    """Returns structured operational context for the selected mode.

    Args:
        mode: MODE_NORMAL or MODE_SURGE_3X.

    Returns:
        Dict with mode, patients DataFrame, counts, and volume multiplier.
    """
    beds_df = load_beds_inventory()
    bed_count = len(beds_df)

    if mode == MODE_SURGE_3X:
        patients = load_surge_cohort()
        volume_multiplier = 3
    else:
        patients = load_normal_cohort()
        volume_multiplier = 1

    return {
        "mode": mode,
        "patients": patients,
        "patient_count": len(patients),
        "bed_count": bed_count,
        "triage_nurse_count": TRIAGE_NURSE_COUNT,
        "volume_multiplier": volume_multiplier,
        "beds_df": beds_df
    }


def compute_surge_summary(
    ranked_queue: List[Dict[str, Any]],
    allocation_results: Dict[str, Any],
    bed_count: int,
    mode: str
) -> Dict[str, Any]:
    """Computes operational pressure summary metrics.

    Args:
        ranked_queue: Ranked patient queue from sequencer.
        allocation_results: Results from bed allocator.
        bed_count: Number of available beds (always 8).
        mode: Operational mode string.

    Returns:
        Dict with all operational pressure metrics.
    """
    patient_count = len(ranked_queue)

    tier_counts = {"Tier A": 0, "Tier B": 0, "Tier C": 0, "Tier D": 0, "Tier E": 0}
    reassess_5 = 0
    reassess_15 = 0
    reassess_30 = 0
    hard_floor_count = 0

    for p in ranked_queue:
        tc = p["queue_tier_code"]
        if tc in tier_counts:
            tier_counts[tc] += 1

        recheck = p["recheck_due_min"]
        if recheck <= 5:
            reassess_5 += 1
        if recheck <= 15:
            reassess_15 += 1
        if recheck <= 30:
            reassess_30 += 1

        if p["protocol_result"].get("triggered"):
            hard_floor_count += 1

    allocated_count = sum(
        1 for p in allocation_results["patient_allocations"]
        if p["allocation_status"] == STATUS_ALLOCATED
    )
    waiting_suitable = sum(
        1 for p in allocation_results["patient_allocations"]
        if p["allocation_status"] == STATUS_WAITING_SUITABLE
    )
    waiting_queue = patient_count - allocated_count - waiting_suitable
    # Remaining waiting patients (WAITING_QUEUE + FAST_TRACK_CANDIDATE_WAITING)

    patients_per_bed = round(patient_count / bed_count, 1) if bed_count > 0 else 0
    patients_per_nurse = patient_count  # single triage nurse

    return {
        "mode": mode,
        "patient_count": patient_count,
        "tier_a_count": tier_counts["Tier A"],
        "tier_b_count": tier_counts["Tier B"],
        "tier_c_count": tier_counts["Tier C"],
        "tier_d_count": tier_counts["Tier D"],
        "tier_e_count": tier_counts["Tier E"],
        "reassess_within_5_min": reassess_5,
        "reassess_within_15_min": reassess_15,
        "reassess_within_30_min": reassess_30,
        "hard_protocol_floor_count": hard_floor_count,
        "allocated_count": allocated_count,
        "waiting_suitable_bed_count": waiting_suitable,
        "waiting_queue_count": waiting_queue,
        "available_bed_count": bed_count,
        "patients_per_bed": patients_per_bed,
        "patients_per_triage_nurse": patients_per_nurse
    }

"""LISA.ai — Static Baseline Simulator (Milestone 6B)

Simulates the standard static emergency department queue policy:
- Primary sort: Initial Triage Level ascending (Level 1 before Level 2, etc.)
- Secondary sort: Arrival Waiting Time descending (FIFO within same triage level)

Does NOT use LISA Risk-of-Wait, deterioration slope, confidence, or Sequence Score.
"""

from typing import Any, Dict, List, Union
import pandas as pd


def rank_static_baseline_queue(cohort_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Ranks the cohort using a static triage level + FIFO policy.

    Args:
        cohort_df: DataFrame of simulated ED patients.

    Returns:
        List of patient records sorted by static baseline priority.
    """
    patients_list: List[Dict[str, Any]] = []

    for idx, row in cohort_df.iterrows():
        patient_token = str(row.get("patient_token", f"IDX_{idx}"))
        
        # Initial triage level (default to 5 if missing/invalid)
        raw_level = row.get("initial_triage_level", 5)
        try:
            triage_level = int(raw_level) if pd.notna(raw_level) else 5
        except (ValueError, TypeError):
            triage_level = 5

        # Arrival elapsed time
        raw_arr = row.get("arrival_minutes_ago", 0)
        try:
            arrival_minutes = int(raw_arr) if pd.notna(raw_arr) else 0
        except (ValueError, TypeError):
            arrival_minutes = 0

        patient_rec = dict(row)
        patient_rec.update({
            "patient_token": patient_token,
            "_original_idx": idx,
            "initial_triage_level": triage_level,
            "arrival_minutes_ago": arrival_minutes,
            "baseline_reason": f"Initial triage Level {triage_level}; FIFO within triage category ({arrival_minutes} min wait)"
        })
        patients_list.append(patient_rec)

    # Static Baseline Sort:
    # 1. Initial Triage Level ascending (Level 1 first)
    # 2. Arrival minutes ago descending (longer wait first within level = FIFO)
    # 3. Original index ascending (stable tie-breaker)
    def static_sort_key(p: Dict[str, Any]):
        return (
            p["initial_triage_level"],
            -p["arrival_minutes_ago"],
            p["_original_idx"]
        )

    patients_list.sort(key=static_sort_key)

    # Assign 1-indexed baseline rank
    for rank_idx, p in enumerate(patients_list, start=1):
        p["baseline_rank"] = rank_idx

    return patients_list

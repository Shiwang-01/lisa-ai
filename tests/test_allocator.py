import os
import pandas as pd
import pytest

from lisa.sequencer import rank_waiting_queue
from lisa.allocator import (
    load_beds_inventory,
    determine_patient_resource_profile,
    allocate_available_beds,
    BED_TYPE_RESUS,
    BED_TYPE_MONITORED,
    BED_TYPE_GENERAL,
    BED_TYPE_FAST_TRACK,
    STATUS_ALLOCATED,
    STATUS_WAITING_SUITABLE
)

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "seed_patients.csv")
BEDS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "seed_beds.csv")


@pytest.fixture
def seed_df():
    return pd.read_csv(DATA_PATH)


@pytest.fixture
def beds_df():
    return load_beds_inventory(BEDS_PATH)


def test_exactly_8_beds_load(beds_df):
    """Test 1: Exactly 8 simulated beds load."""
    assert len(beds_df) == 8


def test_bed_ids_are_unique(beds_df):
    """Test 2: Bed IDs are unique."""
    assert len(beds_df["bed_id"].unique()) == len(beds_df)


def test_allocation_is_deterministic(seed_df, beds_df):
    """Test 3: Allocation is 100% deterministic."""
    queue = rank_waiting_queue(seed_df)
    res1 = allocate_available_beds(queue, beds_df)
    res2 = allocate_available_beds(queue, beds_df)

    b1 = [(b["bed_id"], b["recommended_patient"]) for b in res1["allocated_beds"]]
    b2 = [(b["bed_id"], b["recommended_patient"]) for b in res2["allocated_beds"]]
    assert b1 == b2


def test_no_duplicate_patient_allocations(seed_df, beds_df):
    """Test 4: No patient receives more than one bed."""
    queue = rank_waiting_queue(seed_df)
    alloc = allocate_available_beds(queue, beds_df)

    assigned_tokens = [
        p["patient_token"] for p in alloc["patient_allocations"]
        if p["bed_id"] is not None
    ]
    assert len(assigned_tokens) == len(set(assigned_tokens))


def test_no_duplicate_bed_allocations(seed_df, beds_df):
    """Test 5: No bed receives more than one patient."""
    queue = rank_waiting_queue(seed_df)
    alloc = allocate_available_beds(queue, beds_df)

    assigned_beds = [
        p["bed_id"] for p in alloc["patient_allocations"]
        if p["bed_id"] is not None
    ]
    assert len(assigned_beds) == len(set(assigned_beds))


def test_no_incompatible_allocations(seed_df, beds_df):
    """Test 6: No patient is knowingly assigned an incompatible bed type."""
    queue = rank_waiting_queue(seed_df)
    alloc = allocate_available_beds(queue, beds_df)

    for p in alloc["patient_allocations"]:
        if p["bed_type"]:
            assert p["bed_type"] not in p["incompatible_bed_types"], (
                f"Patient {p['patient_token']} assigned incompatible bed {p['bed_type']}"
            )


def test_max_allocations_bounded_by_beds(seed_df, beds_df):
    """Test 7: Number of allocated patients does not exceed number of available beds."""
    queue = rank_waiting_queue(seed_df)
    alloc = allocate_available_beds(queue, beds_df)

    allocated_count = sum(1 for p in alloc["patient_allocations"] if p["bed_id"] is not None)
    assert allocated_count <= len(beds_df)


def test_level_1_2_protocol_floor_never_fast_track(seed_df, beds_df):
    """Test 8: Level 1 and Level 2 protocol-floor patients are NEVER assigned Fast-track."""
    queue = rank_waiting_queue(seed_df)
    alloc = allocate_available_beds(queue, beds_df)

    for p in alloc["patient_allocations"]:
        orig_p = next(x for x in queue if x["patient_token"] == p["patient_token"])
        fl = orig_p["protocol_result"].get("floor_level") if orig_p["protocol_result"].get("triggered") else None
        if fl in [1, 2]:
            assert p["bed_type"] != BED_TYPE_FAST_TRACK
            assert BED_TYPE_FAST_TRACK in p["incompatible_bed_types"]


def test_stable_low_acuity_is_fast_track_compatible(seed_df):
    """Test 9: Stable low-acuity injury (A127) is Fast-track compatible."""
    p127 = seed_df[seed_df["patient_token"] == "A127"].iloc[0]
    queue = rank_waiting_queue(seed_df)
    p127_queued = next(x for x in queue if x["patient_token"] == "A127")

    profile = determine_patient_resource_profile(
        p127,
        p127_queued["protocol_result"],
        p127_queued["risk_result"],
        p127_queued["queue_tier_code"]
    )
    assert BED_TYPE_FAST_TRACK in profile["preferred_bed_types"]
    assert BED_TYPE_FAST_TRACK in profile["acceptable_bed_types"]
    assert BED_TYPE_FAST_TRACK not in profile["incompatible_bed_types"]


def test_resource_preservation_synthetic_scenario():
    """Test 10: Patient A (General/Fast-track) and Patient B (General only) with 1 General and 1 Fast-track bed.
    Allocator must preserve General for Patient B and allocate Fast-track to Patient A.
    """
    patient_a = {
        "patient_token": "PATIENT_A",
        "priority_rank": 1,
        "queue_tier": "Tier E — Lower Current Wait-Risk",
        "queue_tier_code": "Tier E",
        "sequence_score": 25,
        "current_risk": 15,
        "recheck_due_min": 60,
        "arrival_minutes_ago": 40,
        "complaint_text": "Ankle sprain, stable",
        "case_notes": "Mild sprain",
        "resource_need": "Ice pack",
        "visible_distress": "Mild",
        "mental_status": "Alert",
        "protocol_result": {"triggered": False, "floor_level": None},
        "risk_result": {"current_risk": 15, "risk_60_min": 18, "confidence": 100, "recheck_due_min": 60, "time_to_breach_min": None}
    }

    patient_b = {
        "patient_token": "PATIENT_B",
        "priority_rank": 2,
        "queue_tier": "Tier C — Rising Wait-Risk",
        "queue_tier_code": "Tier C",
        "sequence_score": 40,
        "current_risk": 45,
        "recheck_due_min": 15,
        "arrival_minutes_ago": 20,
        "complaint_text": "Abdominal pain, nausea",
        "case_notes": "Abdominal pain with worsening symptoms, examination needed",
        "resource_need": "IV line, abdominal ultrasound",
        "visible_distress": "Moderate",
        "mental_status": "Alert",
        "protocol_result": {"triggered": False, "floor_level": None},
        "risk_result": {"current_risk": 45, "risk_60_min": 55, "confidence": 95, "recheck_due_min": 15, "time_to_breach_min": 100}
    }

    limited_beds = pd.DataFrame([
        {"bed_id": "G01", "bed_type": BED_TYPE_GENERAL, "status": "Available"},
        {"bed_id": "F01", "bed_type": BED_TYPE_FAST_TRACK, "status": "Available"}
    ])

    alloc = allocate_available_beds([patient_a, patient_b], limited_beds)

    a_alloc = next(p for p in alloc["patient_allocations"] if p["patient_token"] == "PATIENT_A")
    b_alloc = next(p for p in alloc["patient_allocations"] if p["patient_token"] == "PATIENT_B")

    # Patient A takes Fast-track F01, preserving General G01 for Patient B
    assert a_alloc["bed_id"] == "F01"
    assert a_alloc["bed_type"] == BED_TYPE_FAST_TRACK
    assert b_alloc["bed_id"] == "G01"
    assert b_alloc["bed_type"] == BED_TYPE_GENERAL


def test_incompatible_capacity_leaves_urgent_patient_unallocated():
    """Test 11: Fast-track-only capacity leaves urgent monitored patient unallocated rather than making unsafe match."""
    urgent_patient = {
        "patient_token": "URGENT_STROKE",
        "priority_rank": 1,
        "queue_tier": "Tier B — Urgent Reassessment",
        "queue_tier_code": "Tier B",
        "sequence_score": 85,
        "current_risk": 70,
        "recheck_due_min": 5,
        "arrival_minutes_ago": 15,
        "complaint_text": "Acute facial droop and slurred speech",
        "case_notes": "Stroke alert",
        "resource_need": "Stat head CT, telemetry",
        "visible_distress": "Moderate",
        "mental_status": "Alert",
        "protocol_result": {"triggered": True, "floor_level": 2, "rule_ids": ["GF-STROKE-01"], "reasons": ["Stroke signs"]},
        "risk_result": {"current_risk": 70, "risk_60_min": 85, "confidence": 100, "recheck_due_min": 5, "time_to_breach_min": 40}
    }

    only_fast_track = pd.DataFrame([
        {"bed_id": "FT01", "bed_type": BED_TYPE_FAST_TRACK, "status": "Available"}
    ])

    alloc = allocate_available_beds([urgent_patient], only_fast_track)
    res = alloc["patient_allocations"][0]

    # Must NOT assign FT01
    assert res["bed_id"] is None
    assert res["bed_type"] is None
    assert res["allocation_status"] == STATUS_WAITING_SUITABLE
    assert "urgent clinician reassessment" in res["allocation_reason"].lower()


def test_high_priority_unallocated_language_requires_urgent_reassessment(seed_df, beds_df):
    """Test 12: High-priority unallocated patients receive explicit urgent reassessment status, not safe waiting."""
    queue = rank_waiting_queue(seed_df)
    alloc = allocate_available_beds(queue, beds_df)

    for p in alloc["waiting_patients"]:
        if p["queue_tier_code"] in ["Tier A", "Tier B"]:
            assert "urgent" in p["allocation_reason"].lower() or "reassessment" in p["allocation_reason"].lower()
            assert "safe" not in p["allocation_reason"].lower()


def test_a132_missing_history_does_not_consume_resus(seed_df):
    """Test 13: A132 (vague weakness, missing history) does NOT require or consume Resus."""
    p132 = seed_df[seed_df["patient_token"] == "A132"].iloc[0]
    queue = rank_waiting_queue(seed_df)
    p132_q = next(x for x in queue if x["patient_token"] == "A132")

    profile = determine_patient_resource_profile(
        p132,
        p132_q["protocol_result"],
        p132_q["risk_result"],
        p132_q["queue_tier_code"]
    )
    assert BED_TYPE_RESUS not in profile["preferred_bed_types"]
    assert BED_TYPE_RESUS not in profile["acceptable_bed_types"]


def test_allocations_contain_human_readable_reasons(seed_df, beds_df):
    """Test 14: All allocations contain human-readable reasons."""
    queue = rank_waiting_queue(seed_df)
    alloc = allocate_available_beds(queue, beds_df)

    for p in alloc["patient_allocations"]:
        assert isinstance(p["allocation_reason"], str)
        assert len(p["allocation_reason"]) > 0


def test_allocation_independent_of_token():
    """Test 15: Allocation logic does NOT depend on patient_token."""
    base_p = {
        "priority_rank": 1,
        "queue_tier": "Tier E — Lower Current Wait-Risk",
        "queue_tier_code": "Tier E",
        "sequence_score": 10,
        "current_risk": 5,
        "recheck_due_min": 60,
        "arrival_minutes_ago": 30,
        "complaint_text": "Ankle sprain",
        "case_notes": "Mild sprain",
        "resource_need": "Ice pack",
        "visible_distress": "Mild",
        "mental_status": "Alert",
        "protocol_result": {"triggered": False, "floor_level": None},
        "risk_result": {"current_risk": 5, "risk_60_min": 8, "confidence": 100, "recheck_due_min": 60, "time_to_breach_min": None}
    }

    p_a = dict(base_p)
    p_a["patient_token"] = "TOKEN_ALPHA"

    p_b = dict(base_p)
    p_b["patient_token"] = "TOKEN_BETA"

    beds = pd.DataFrame([{"bed_id": "B07", "bed_type": BED_TYPE_FAST_TRACK, "status": "Available"}])

    res_a = allocate_available_beds([p_a], beds)["patient_allocations"][0]
    res_b = allocate_available_beds([p_b], beds)["patient_allocations"][0]

    assert res_a["bed_id"] == res_b["bed_id"]
    assert res_a["bed_type"] == res_b["bed_type"]
    assert res_a["allocation_status"] == res_b["allocation_status"]


def test_allocator_explanations_non_diagnostic(seed_df, beds_df):
    """Test 16: Allocator user-facing explanations must NOT contain prohibited diagnostic or procedural terms."""
    queue = rank_waiting_queue(seed_df)
    alloc = allocate_available_beds(queue, beds_df)

    prohibited_terms = [
        "acute abdomen",
        "acs",
        "angina",
        "myocardial infarction",
        "ischemia",
        "sepsis",
        "anaphylaxis",
        "decompensated",
        "iv access",
        "diagnostic workup",
        "treatment",
        "administer medication",
        "resuscitation",
        "telemetry"
    ]

    for p in alloc["patient_allocations"]:
        combined = " ".join([
            p["allocation_reason"],
            " ".join(p["allocation_reasons"]),
        ]).lower()

        for term in prohibited_terms:
            assert term not in combined, (
                f"Prohibited term '{term}' found in allocation explanation "
                f"for patient {p['patient_token']}: '{combined}'"
            )



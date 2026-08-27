import os
import pandas as pd
import pytest

from lisa.protocol_floor import evaluate_protocol_floor
from lisa.risk_engine import evaluate_risk_of_wait
from lisa.sequencer import rank_waiting_queue
from lisa.allocator import load_beds_inventory, allocate_available_beds
from lisa.surge_simulator import (
    load_normal_cohort,
    load_surge_cohort,
    get_operational_mode,
    compute_surge_summary,
    MODE_NORMAL,
    MODE_SURGE_3X
)


@pytest.fixture
def normal_df():
    return load_normal_cohort()


@pytest.fixture
def surge_df():
    return load_surge_cohort()


@pytest.fixture
def beds_df():
    return load_beds_inventory()


def test_normal_cohort_contains_20_patients(normal_df):
    """Test 1: Normal cohort contains exactly 20 patients."""
    assert len(normal_df) == 20


def test_surge_cohort_contains_60_patients(surge_df):
    """Test 2: Surge cohort contains exactly 60 patients."""
    assert len(surge_df) == 60


def test_all_surge_tokens_are_unique(surge_df):
    """Test 3: All 60 Surge patient tokens are unique."""
    assert surge_df["patient_token"].nunique() == 60


def test_a124_to_a143_present_in_both(normal_df, surge_df):
    """Test 4: Original patients A124-A143 are present in both modes."""
    orig_tokens = [f"A{i}" for i in range(124, 144)]
    normal_tokens = set(normal_df["patient_token"])
    surge_tokens = set(surge_df["patient_token"])

    for token in orig_tokens:
        assert token in normal_tokens
        assert token in surge_tokens


def test_original_data_identical_in_normal_and_surge(normal_df, surge_df):
    """Test 5: The original A124-A143 clinical data are identical in Normal and Surge datasets."""
    orig_tokens = [f"A{i}" for i in range(124, 144)]
    normal_sub = normal_df[normal_df["patient_token"].isin(orig_tokens)].sort_values("patient_token").reset_index(drop=True)
    surge_sub = surge_df[surge_df["patient_token"].isin(orig_tokens)].sort_values("patient_token").reset_index(drop=True)

    pd.testing.assert_frame_equal(normal_sub, surge_sub)


def test_a144_to_a183_exist_only_in_surge(normal_df, surge_df):
    """Test 6: A144-A183 exist only in Surge cohort."""
    surge_only_tokens = [f"A{i}" for i in range(144, 184)]
    normal_tokens = set(normal_df["patient_token"])
    surge_tokens = set(surge_df["patient_token"])

    for token in surge_only_tokens:
        assert token not in normal_tokens
        assert token in surge_tokens


def test_deterministic_surge_ranking(surge_df):
    """Test 7: Same Surge input produces identical ranking every time."""
    q1 = rank_waiting_queue(surge_df)
    q2 = rank_waiting_queue(surge_df)

    assert [p["patient_token"] for p in q1] == [p["patient_token"] for p in q2]
    assert [p["sequence_score"] for p in q1] == [p["sequence_score"] for p in q2]


def test_deterministic_surge_allocation(surge_df, beds_df):
    """Test 8: Same Surge input produces identical bed allocation every time."""
    q = rank_waiting_queue(surge_df)
    res1 = allocate_available_beds(q, beds_df)
    res2 = allocate_available_beds(q, beds_df)

    b1 = [(b["bed_id"], b["recommended_patient"]) for b in res1["allocated_beds"]]
    b2 = [(b["bed_id"], b["recommended_patient"]) for b in res2["allocated_beds"]]
    assert b1 == b2


def test_surge_mode_has_exactly_8_beds():
    """Test 9: Surge Mode operational context still has exactly 8 beds."""
    ctx = get_operational_mode(MODE_SURGE_3X)
    assert ctx["bed_count"] == 8
    assert len(ctx["beds_df"]) == 8


def test_surge_mode_never_allocates_more_than_8_patients(surge_df, beds_df):
    """Test 10: Surge Mode never allocates more than 8 patients (available bed capacity)."""
    q = rank_waiting_queue(surge_df)
    res = allocate_available_beds(q, beds_df)

    allocated_count = sum(1 for p in res["patient_allocations"] if p["bed_id"] is not None)
    assert allocated_count <= 8


def test_no_duplicate_allocations_in_surge(surge_df, beds_df):
    """Tests 11 & 12: No duplicate bed or patient allocations in Surge Mode."""
    q = rank_waiting_queue(surge_df)
    res = allocate_available_beds(q, beds_df)

    assigned_beds = [p["bed_id"] for p in res["patient_allocations"] if p["bed_id"] is not None]
    assigned_tokens = [p["patient_token"] for p in res["patient_allocations"] if p["bed_id"] is not None]

    assert len(assigned_beds) == len(set(assigned_beds))
    assert len(assigned_tokens) == len(set(assigned_tokens))


def test_clinical_facts_unchanged_by_surge(normal_df, surge_df):
    """Tests 13, 14, 15, 16: Clinical outputs (protocol floor, current risk, confidence, recheck) remain identical."""
    for token in [f"A{i}" for i in range(124, 144)]:
        row_norm = normal_df[normal_df["patient_token"] == token].iloc[0]
        row_surge = surge_df[surge_df["patient_token"] == token].iloc[0]

        pf_norm = evaluate_protocol_floor(row_norm)
        pf_surge = evaluate_protocol_floor(row_surge)
        assert pf_norm == pf_surge

        rw_norm = evaluate_risk_of_wait(row_norm, pf_norm)
        rw_surge = evaluate_risk_of_wait(row_surge, pf_surge)

        assert rw_norm["current_risk"] == rw_surge["current_risk"]
        assert rw_norm["risk_60_min"] == rw_surge["risk_60_min"]
        assert rw_norm["confidence"] == rw_surge["confidence"]
        assert rw_norm["recheck_due_min"] == rw_surge["recheck_due_min"]


def test_surge_summary_metrics_reconcile(surge_df, beds_df):
    """Tests 19, 20, 21: Surge summary counts reconcile correctly to 60 patients."""
    q = rank_waiting_queue(surge_df)
    res = allocate_available_beds(q, beds_df)
    summary = compute_surge_summary(q, res, len(beds_df), MODE_SURGE_3X)

    assert summary["patient_count"] == 60
    assert (
        summary["tier_a_count"]
        + summary["tier_b_count"]
        + summary["tier_c_count"]
        + summary["tier_d_count"]
        + summary["tier_e_count"]
    ) == 60

    assert (
        summary["allocated_count"]
        + summary["waiting_suitable_bed_count"]
        + summary["waiting_queue_count"]
    ) == 60

    assert summary["available_bed_count"] == 8
    assert summary["patients_per_bed"] == round(60 / 8, 1)
    assert summary["patients_per_triage_nurse"] == 60


def test_safety_language_in_surge_dataset(surge_df, beds_df):
    """Test 26: Scan all 40 new records and surge allocation explanations for prohibited diagnostic and procedural terms."""
    prohibited_diagnostic_terms = [
        "acute abdomen",
        "acs",
        "angina",
        "myocardial infarction",
        "ischemia",
        "sepsis",
        "anaphylaxis",
        "decompensated"
    ]

    prohibited_allocation_terms = prohibited_diagnostic_terms + [
        "iv access",
        "diagnostic workup",
        "treatment",
        "administer medication",
        "resuscitation",
        "telemetry"
    ]

    # Check 40 new patient case notes and complaints for prohibited diagnostic terms
    for _, row in surge_df.iterrows():
        text = f"{row['complaint_text']} {row['case_notes']}".lower()
        for term in prohibited_diagnostic_terms:
            assert term not in text, f"Prohibited term '{term}' found in {row['patient_token']}: {text}"

    # Check user-facing allocation explanations for all 60 patients
    q = rank_waiting_queue(surge_df)
    res = allocate_available_beds(q, beds_df)
    for p in res["patient_allocations"]:
        expl = " ".join([p["allocation_reason"]] + p["allocation_reasons"]).lower()
        for term in prohibited_allocation_terms:
            assert term not in expl, f"Prohibited term '{term}' in allocation explanation for {p['patient_token']}: {expl}"


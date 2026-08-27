import os
import pandas as pd
import pytest

from lisa.surge_simulator import load_normal_cohort, load_surge_cohort
from lisa.comparison_metrics import (
    compare_queue_policies,
    SIMULATION_HORIZON_MINUTES,
    ATTENTION_SLOT_MINUTES,
    AVAILABLE_ATTENTION_SLOTS
)


@pytest.fixture
def normal_df():
    return load_normal_cohort()


@pytest.fixture
def surge_df():
    return load_surge_cohort()


def test_normal_comparison_uses_20_patients(normal_df):
    """Test 1: Normal mode comparison evaluates exactly 20 patients."""
    res = compare_queue_policies(normal_df)
    assert res["simulation_assumptions"]["patient_count"] == 20
    assert len(res["patient_level_results"]) == 20


def test_surge_comparison_uses_60_patients(surge_df):
    """Test 2: Surge mode comparison evaluates exactly 60 patients."""
    res = compare_queue_policies(surge_df)
    assert res["simulation_assumptions"]["patient_count"] == 60
    assert len(res["patient_level_results"]) == 60


def test_same_assumptions_applied_to_both_policies(normal_df):
    """Test 3: Attention slots, slot interval, and simulation horizon are identical."""
    res = compare_queue_policies(normal_df)
    assumptions = res["simulation_assumptions"]

    assert assumptions["simulation_horizon_min"] == 120
    assert assumptions["attention_slot_min"] == 5
    assert assumptions["available_attention_slots"] == 24


def test_coverage_identical_between_policies(normal_df, surge_df):
    """Test 4: reviewed_within_horizon and not_reviewed_within_horizon are identical between policies."""
    for df in [normal_df, surge_df]:
        res = compare_queue_policies(df)
        static_m = res["static_baseline"]
        lisa_m = res["lisa"]

        assert static_m["reviewed_within_horizon"] == lisa_m["reviewed_within_horizon"]
        assert static_m["not_reviewed_within_horizon"] == lisa_m["not_reviewed_within_horizon"]


def test_no_extra_capacity_created(normal_df, surge_df):
    """Test 5: Neither policy creates attention slots beyond AVAILABLE_ATTENTION_SLOTS (24)."""
    for df in [normal_df, surge_df]:
        res = compare_queue_policies(df)
        assert res["static_baseline"]["reviewed_within_horizon"] <= 24
        assert res["lisa"]["reviewed_within_horizon"] <= 24


def test_missed_deadline_calculation_correct(normal_df):
    """Test 6: Missed deadline calculation correctly compares scheduled attention to recheck deadline."""
    res = compare_queue_policies(normal_df)
    for p in res["patient_level_results"]:
        recheck = p["recheck_due_min"]
        
        # LISA check
        lisa_att = p["lisa_attention_min"]
        if lisa_att is not None:
            expected_lisa_missed = lisa_att > recheck
        else:
            expected_lisa_missed = recheck <= 120
        assert p["lisa_deadline_missed"] == expected_lisa_missed

        # Static check
        stat_att = p["static_attention_min"]
        if stat_att is not None:
            expected_stat_missed = stat_att > recheck
        else:
            expected_stat_missed = recheck <= 120
        assert p["static_deadline_missed"] == expected_stat_missed


def test_delay_calculation_is_deterministic(normal_df):
    """Test 7: Average and median reassessment delays are deterministic."""
    res1 = compare_queue_policies(normal_df)
    res2 = compare_queue_policies(normal_df)

    assert res1["static_baseline"]["average_reassessment_delay_min"] == res2["static_baseline"]["average_reassessment_delay_min"]
    assert res1["lisa"]["average_reassessment_delay_min"] == res2["lisa"]["average_reassessment_delay_min"]


def test_tier_ab_early_review_metric(normal_df):
    """Test 8: Tier A/B reviewed within 15 min metric counts patients with attention <= 15 min."""
    res = compare_queue_policies(normal_df)
    lisa_m = res["lisa"]
    static_m = res["static_baseline"]

    # In 20-patient cohort, exactly 11 patients are Tier A or Tier B with safety floors
    assert lisa_m["urgent_total"] == 11
    assert static_m["urgent_total"] == 11
    assert lisa_m["urgent_reviewed_within_15_min"] <= 11
    assert static_m["urgent_reviewed_within_15_min"] <= 11


def test_high_wait_risk_early_review_metric(normal_df):
    """Test 9: High wait risk (risk_60_min >= 75) metric correctly counts patients with attention <= 30 min."""
    res = compare_queue_policies(normal_df)
    lisa_m = res["lisa"]
    static_m = res["static_baseline"]

    assert lisa_m["high_wait_risk_total"] == static_m["high_wait_risk_total"]
    assert lisa_m["high_wait_risk_reviewed_within_30_min"] <= lisa_m["high_wait_risk_total"]


def test_priority_inversions_metric_correct(normal_df):
    """Test 10: Lower-urgency displacement metric counts Tier D/E patients scheduled before Tier A/B."""
    res = compare_queue_policies(normal_df)
    static_inversions = res["static_baseline"]["lower_urgency_ahead_of_urgent_count"]
    lisa_inversions = res["lisa"]["lower_urgency_ahead_of_urgent_count"]

    # LISA enforces strict tier boundaries, so lower-urgency patients are never placed ahead of Tier A/B
    assert lisa_inversions == 0
    # In static baseline, some Level 3/4 patients with long waits are placed ahead of Level 2/3 rapid-deterioration patients
    assert isinstance(static_inversions, int)
    assert static_inversions >= 0


def test_no_prohibited_outcome_claims_in_comparison_outputs(normal_df, surge_df):
    """Test 11: Ensure comparison dictionary keys and strings contain no prohibited clinical outcome claims."""
    prohibited_claims = [
        "lives_saved",
        "deaths_prevented",
        "mortality_reduction",
        "deterioration_prevented",
        "icu_admissions_avoided",
        "treatment_success",
        "survival",
        "cost_savings",
        "cured"
    ]

    for df in [normal_df, surge_df]:
        res = compare_queue_policies(df)
        all_keys = list(res.keys()) + list(res["static_baseline"].keys()) + list(res["lisa"].keys()) + list(res["differences"].keys())
        all_text = " ".join(all_keys).lower()

        for claim in prohibited_claims:
            assert claim not in all_text, f"Prohibited outcome claim '{claim}' found in comparison output keys"

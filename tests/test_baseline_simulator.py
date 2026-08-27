import os
import pandas as pd
import pytest

from lisa.baseline_simulator import rank_static_baseline_queue
from lisa.surge_simulator import load_normal_cohort, load_surge_cohort


@pytest.fixture
def normal_df():
    return load_normal_cohort()


@pytest.fixture
def surge_df():
    return load_surge_cohort()


def test_baseline_ranking_is_deterministic(normal_df):
    """Test 1: Static baseline ranking is deterministic."""
    q1 = rank_static_baseline_queue(normal_df)
    q2 = rank_static_baseline_queue(normal_df)

    tokens1 = [p["patient_token"] for p in q1]
    tokens2 = [p["patient_token"] for p in q2]
    ranks1 = [p["baseline_rank"] for p in q1]
    ranks2 = [p["baseline_rank"] for p in q2]

    assert tokens1 == tokens2
    assert ranks1 == ranks2


def test_baseline_uses_initial_triage_level(normal_df):
    """Test 2: Baseline primary sort is initial_triage_level ascending."""
    q = rank_static_baseline_queue(normal_df)
    triage_levels = [p["initial_triage_level"] for p in q]

    # Must be monotonically non-decreasing
    for i in range(len(triage_levels) - 1):
        assert triage_levels[i] <= triage_levels[i + 1], (
            f"Triage level out of order at index {i}: {triage_levels[i]} > {triage_levels[i+1]}"
        )


def test_baseline_uses_fifo_within_same_triage_level(normal_df):
    """Test 3: Within the same initial triage level, older arrival waits are ranked before newer arrivals (FIFO)."""
    q = rank_static_baseline_queue(normal_df)

    for i in range(len(q) - 1):
        p1 = q[i]
        p2 = q[i + 1]
        if p1["initial_triage_level"] == p2["initial_triage_level"]:
            assert p1["arrival_minutes_ago"] >= p2["arrival_minutes_ago"], (
                f"FIFO violated between {p1['patient_token']} ({p1['arrival_minutes_ago']}m) "
                f"and {p2['patient_token']} ({p2['arrival_minutes_ago']}m)"
            )


def test_baseline_does_not_use_sequence_score(normal_df):
    """Test 4: Static baseline does NOT use Sequence Score for sorting."""
    # Create two synthetic patients: one with low triage level and low score, one with higher triage level and high score
    df = pd.DataFrame([
        {
            "patient_token": "P_HIGH_TRIAGE",
            "initial_triage_level": 4,
            "arrival_minutes_ago": 60,
            "sequence_score": 99  # Fake score attribute
        },
        {
            "patient_token": "P_LOW_TRIAGE",
            "initial_triage_level": 1,
            "arrival_minutes_ago": 10,
            "sequence_score": 10  # Fake score attribute
        }
    ])
    q = rank_static_baseline_queue(df)
    # Level 1 must be ranked before Level 4 regardless of sequence score
    assert q[0]["patient_token"] == "P_LOW_TRIAGE"
    assert q[1]["patient_token"] == "P_HIGH_TRIAGE"


def test_baseline_does_not_use_lisa_risk_values(normal_df):
    """Test 5: Baseline does NOT use LISA risk values or floors for sorting."""
    # A125 (Level 4, 40m wait) and A134 (Level 4, 50m wait)
    # Under static baseline, A134 (50m) must rank before A125 (40m) even though A125 has higher risk
    q = rank_static_baseline_queue(normal_df)
    idx_a134 = next(i for i, p in enumerate(q) if p["patient_token"] == "A134")
    idx_a125 = next(i for i, p in enumerate(q) if p["patient_token"] == "A125")

    # In baseline, A134 arrives 50 min ago > A125 arrives 40 min ago within Level 4 -> A134 is ranked first
    assert idx_a134 < idx_a125


def test_baseline_output_fields(normal_df):
    """Test 6: Baseline output has required fields."""
    q = rank_static_baseline_queue(normal_df)
    assert len(q) == 20
    for p in q:
        assert "patient_token" in p
        assert "baseline_rank" in p
        assert "initial_triage_level" in p
        assert "arrival_minutes_ago" in p
        assert "baseline_reason" in p

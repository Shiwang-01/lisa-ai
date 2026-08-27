import os
import pandas as pd
import pytest

from lisa.protocol_floor import evaluate_protocol_floor
from lisa.risk_engine import evaluate_risk_of_wait
from lisa.sequencer import (
    rank_waiting_queue,
    assign_queue_tier,
    calculate_sequence_score,
    TIER_A_CODE,
    TIER_B_CODE,
    TIER_C_CODE,
    TIER_D_CODE,
    TIER_E_CODE
)

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "seed_patients.csv")


@pytest.fixture
def seed_df():
    return pd.read_csv(DATA_PATH)


def test_sequence_score_bounded_0_to_100(seed_df):
    """Test 1: Sequence Score stays between 0 and 100 for all patients."""
    queue = rank_waiting_queue(seed_df)
    for p in queue:
        assert 0 <= p["sequence_score"] <= 100, f"Score out of bounds: {p['sequence_score']} for {p['patient_token']}"


def test_deterministic_ranking(seed_df):
    """Test 2: Same cohort input returns identical ranking every time."""
    q1 = rank_waiting_queue(seed_df)
    q2 = rank_waiting_queue(seed_df)

    tokens1 = [p["patient_token"] for p in q1]
    tokens2 = [p["patient_token"] for p in q2]
    scores1 = [p["sequence_score"] for p in q1]
    scores2 = [p["sequence_score"] for p in q2]

    assert tokens1 == tokens2
    assert scores1 == scores2


def test_protocol_floor_level_1_maps_to_tier_a():
    """Test 5: Protocol Floor Level 1 maps directly to Tier A."""
    patient = {
        "age": 50,
        "complaint_text": "Unresponsive, severe trauma with massive hemorrhage",
        "mental_status": "Unresponsive",
        "visible_distress": "Severe",
        "arrival_minutes_ago": 10
    }
    floor_res = {"triggered": True, "floor_level": 1, "rule_ids": ["GF-CRITICAL-01"], "reasons": ["Critical"]}
    risk_res = {"current_risk": 95, "risk_60_min": 100, "confidence": 90, "recheck_due_min": 5, "time_to_breach_min": 0}

    tier = assign_queue_tier(patient, floor_res, risk_res)
    assert tier["tier_code"] == TIER_A_CODE


def test_protocol_floor_level_2_cannot_map_below_tier_b(seed_df):
    """Test 6: Protocol Floor Level 2 cannot map below Tier B (must be Tier A or Tier B)."""
    queue = rank_waiting_queue(seed_df)
    for p in queue:
        if p["protocol_result"]["triggered"] and p["protocol_result"]["floor_level"] == 2:
            assert p["queue_tier_code"] in [TIER_A_CODE, TIER_B_CODE], (
                f"Protocol Floor Level 2 patient {p['patient_token']} mapped to invalid {p['queue_tier_code']}"
            )


def test_a129_ranks_above_a141(seed_df):
    """Test 7: A129 (confusion+hypotension+fever) ranks substantially above A141 (knee injury)."""
    queue = rank_waiting_queue(seed_df)
    ranks = {p["patient_token"]: p["priority_rank"] for p in queue}
    assert ranks["A129"] < ranks["A141"]


def test_a124_ranks_above_a127(seed_df):
    """Test 8: A124 (respiratory concern) ranks substantially above A127 (ankle sprain)."""
    queue = rank_waiting_queue(seed_df)
    ranks = {p["patient_token"]: p["priority_rank"] for p in queue}
    assert ranks["A124"] < ranks["A127"]


def test_a125_ranks_above_a127_urgency(seed_df):
    """Test 9: A125 (atypical sweating/diabetes) ranks above A127 (ankle sprain)."""
    queue = rank_waiting_queue(seed_df)
    ranks = {p["patient_token"]: p["priority_rank"] for p in queue}
    assert ranks["A125"] < ranks["A127"]


def test_a143_greater_urgency_than_low_acuity_control(seed_df):
    """Test 10: A143 (vomiting/diarrhea+tachycardia) receives greater sequencing urgency than A127/A141."""
    queue = rank_waiting_queue(seed_df)
    ranks = {p["patient_token"]: p["priority_rank"] for p in queue}
    assert ranks["A143"] < ranks["A127"]
    assert ranks["A143"] < ranks["A141"]


def test_very_long_wait_cannot_overtake_protocol_floor():
    """Test 11: Very long waiting time alone (e.g. 240 mins) does NOT outrank an urgent Level 2 floor case."""
    urgent_short_wait = {
        "patient_token": "URGENT_SHORT",
        "age": 30,
        "complaint_text": "Deep laceration with active bleeding",
        "heart_rate": 95,
        "respiratory_rate": 18,
        "systolic_bp": 120,
        "diastolic_bp": 80,
        "spo2": 99,
        "temperature": 37.0,
        "pain_score": 7,
        "mental_status": "Alert",
        "visible_distress": "Moderate",
        "known_history": "None",
        "prior_record_available": "Yes",
        "pregnancy_status": "Not Applicable",
        "arrival_minutes_ago": 10,
        "resource_need": "Suturing, pressure dressing",
        "case_notes": "Bright red active bleeding"
    }

    stable_long_wait = {
        "patient_token": "STABLE_LONG",
        "age": 25,
        "complaint_text": "Twisted ankle while walking, isolated soreness",
        "heart_rate": 70,
        "respiratory_rate": 14,
        "systolic_bp": 120,
        "diastolic_bp": 78,
        "spo2": 99,
        "temperature": 36.6,
        "pain_score": 4,
        "mental_status": "Alert",
        "visible_distress": "Mild",
        "known_history": "None",
        "prior_record_available": "Yes",
        "pregnancy_status": "Not Applicable",
        "arrival_minutes_ago": 240,  # 4 hours waiting
        "resource_need": "Ice pack, x-ray",
        "case_notes": "Isolated musculoskeletal injury"
    }

    test_df = pd.DataFrame([stable_long_wait, urgent_short_wait])
    ranked = rank_waiting_queue(test_df)

    # Urgent patient with active floor MUST rank #1 despite waiting only 10 mins vs 240 mins
    assert ranked[0]["patient_token"] == "URGENT_SHORT"
    assert ranked[1]["patient_token"] == "STABLE_LONG"
    assert ranked[0]["queue_tier_code"] in [TIER_A_CODE, TIER_B_CODE]
    assert ranked[1]["queue_tier_code"] == TIER_E_CODE


def test_lower_confidence_never_decreases_sequencing_urgency():
    """Test 12: Lower confidence (increased uncertainty) never decreases sequencing urgency."""
    base_patient = {
        "arrival_minutes_ago": 30,
        "patient_token": "P_BASE"
    }
    risk_high_conf = {
        "current_risk": 40,
        "risk_60_min": 50,
        "confidence": 95,
        "time_to_breach_min": 90,
        "recheck_due_min": 30
    }
    risk_low_conf = {
        "current_risk": 40,
        "risk_60_min": 50,
        "confidence": 50,  # lower confidence
        "time_to_breach_min": 90,
        "recheck_due_min": 30
    }

    s_high = calculate_sequence_score(base_patient, risk_high_conf)
    s_low = calculate_sequence_score(base_patient, risk_low_conf)

    # Lower confidence produces higher uncertainty factor, thus higher sequence score
    assert s_low["sequence_score"] >= s_high["sequence_score"]


def test_sequence_explanations_returned(seed_df):
    """Test 13: Sequence explanations and codes are returned for all patients."""
    queue = rank_waiting_queue(seed_df)
    for p in queue:
        assert isinstance(p["sequence_reasons"], list)
        assert len(p["sequence_reasons"]) > 0
        assert isinstance(p["sequence_codes"], list)
        assert len(p["sequence_codes"]) > 0


def test_ranking_independent_of_token():
    """Test 14: Ranking does NOT use patient_token as a clinical priority feature."""
    p1 = {
        "patient_token": "ZZZ_TOKEN",
        "age": 75,
        "complaint_text": "Acute confusion, fall, hypotensive",
        "heart_rate": 112,
        "respiratory_rate": 24,
        "systolic_bp": 88,
        "diastolic_bp": 54,
        "spo2": 95,
        "temperature": 38.6,
        "pain_score": 4,
        "mental_status": "Confused",
        "visible_distress": "Moderate",
        "known_history": "Dementia, CKD",
        "prior_record_available": "Yes",
        "pregnancy_status": "Not Applicable",
        "arrival_minutes_ago": 45,
        "case_notes": "Hypotensive and febrile with altered mental status",
        "resource_need": "IV fluids, blood cultures, broad spectrum workup"
    }
    p2 = {
        "patient_token": "AAA_TOKEN",
        "age": 20,
        "complaint_text": "Ankle sprain",
        "heart_rate": 70,
        "respiratory_rate": 14,
        "systolic_bp": 120,
        "diastolic_bp": 75,
        "spo2": 99,
        "temperature": 36.6,
        "pain_score": 3,
        "mental_status": "Alert",
        "visible_distress": "Mild",
        "known_history": "None",
        "prior_record_available": "Yes",
        "pregnancy_status": "Not Applicable",
        "arrival_minutes_ago": 15,
        "case_notes": "Mild sprain",
        "resource_need": "Ice pack"
    }

    df1 = pd.DataFrame([p1, p2])
    q1 = rank_waiting_queue(df1)

    # p1 with ZZZ token still ranks #1 over AAA token because clinical safety dominates alphabetical order
    assert q1[0]["patient_token"] == "ZZZ_TOKEN"
    assert q1[1]["patient_token"] == "AAA_TOKEN"


def test_cohort_returns_exact_20_entries(seed_df):
    """Test 15: Original 20-patient cohort returns exactly 20 ranked entries."""
    queue = rank_waiting_queue(seed_df)
    assert len(queue) == 20
    ranks = [p["priority_rank"] for p in queue]
    assert ranks == list(range(1, 21))


def test_every_ranked_patient_has_required_fields(seed_df):
    """Test 16: Every ranked patient receives rank, tier, score, and recommended queue action."""
    queue = rank_waiting_queue(seed_df)
    required_fields = [
        "priority_rank",
        "patient_token",
        "queue_tier",
        "queue_tier_code",
        "sequence_score",
        "recommended_queue_action",
        "current_risk",
        "risk_60_min",
        "confidence",
        "recheck_due_min",
        "arrival_minutes_ago"
    ]
    for p in queue:
        for field in required_fields:
            assert field in p, f"Missing {field} in ranked entry {p.get('patient_token')}"


def test_initial_clinician_triage_level_1_cannot_map_below_tier_a():
    """Test 17: Initial clinician triage Level 1 cannot map below Tier A."""
    patient = {"initial_triage_level": 1, "arrival_minutes_ago": 10}
    floor_res = {"triggered": False, "floor_level": None}
    risk_res = {"current_risk": 20, "risk_60_min": 30, "confidence": 100, "recheck_due_min": 60, "time_to_breach_min": None}

    tier = assign_queue_tier(patient, floor_res, risk_res)
    assert tier["tier_code"] == TIER_A_CODE


def test_initial_clinician_triage_level_2_cannot_map_below_tier_b():
    """Test 18: Initial clinician triage Level 2 cannot map below Tier B."""
    patient = {"initial_triage_level": 2, "arrival_minutes_ago": 10}
    floor_res = {"triggered": False, "floor_level": None}
    risk_res = {"current_risk": 20, "risk_60_min": 30, "confidence": 100, "recheck_due_min": 60, "time_to_breach_min": None}

    tier = assign_queue_tier(patient, floor_res, risk_res)
    assert tier["tier_code"] in [TIER_A_CODE, TIER_B_CODE]


def test_effective_floor_resolution_clinician_precedence():
    """Test 19: If initial triage is Level 1 and protocol floor is Level 2, effective floor is Level 1."""
    patient = {"initial_triage_level": 1}
    floor_res = {"triggered": True, "floor_level": 2}
    risk_res = {"current_risk": 50, "risk_60_min": 65, "confidence": 95, "recheck_due_min": 15, "time_to_breach_min": None}

    tier = assign_queue_tier(patient, floor_res, risk_res)
    assert tier["tier_code"] == TIER_A_CODE
    assert tier["safety_info"]["effective_safety_floor"] == 1
    assert tier["safety_info"]["effective_safety_floor_source"] == "CLINICIAN_TRIAGE"


def test_effective_floor_resolution_protocol_precedence():
    """Test 20: If initial triage is Level 3 and protocol floor is Level 2, effective floor is Level 2."""
    patient = {"initial_triage_level": 3}
    floor_res = {"triggered": True, "floor_level": 2}
    risk_res = {"current_risk": 50, "risk_60_min": 65, "confidence": 95, "recheck_due_min": 15, "time_to_breach_min": None}

    tier = assign_queue_tier(patient, floor_res, risk_res)
    assert tier["tier_code"] == TIER_B_CODE
    assert tier["safety_info"]["effective_safety_floor"] == 2
    assert tier["safety_info"]["effective_safety_floor_source"] == "PROTOCOL_GUARDRAIL"


def test_clinician_level_1_sequenced_ahead_of_non_level_1():
    """Test 21: A clinician Level 1 patient is sequenced ahead of an otherwise comparable patient with no Level 1 floor."""
    p_l1 = {
        "patient_token": "P_CLINICIAN_L1",
        "initial_triage_level": 1,
        "age": 60,
        "complaint_text": "Focal weakness",
        "mental_status": "Alert",
        "visible_distress": "Moderate",
        "arrival_minutes_ago": 15,
        "case_notes": "Mild deficit",
        "resource_need": "Observation"
    }
    p_l2 = {
        "patient_token": "P_RISK_L2",
        "initial_triage_level": 2,
        "age": 60,
        "complaint_text": "Severe breathlessness",
        "mental_status": "Alert",
        "visible_distress": "Moderate",
        "arrival_minutes_ago": 15,
        "case_notes": "Wheezing",
        "resource_need": "Nebulization"
    }

    df = pd.DataFrame([p_l2, p_l1])
    ranked = rank_waiting_queue(df)
    assert ranked[0]["patient_token"] == "P_CLINICIAN_L1"
    assert ranked[1]["patient_token"] == "P_RISK_L2"


def test_a135_effective_safety_floor_and_tier_a(seed_df):
    """Test 22: A135 (initial triage 1, protocol floor 2) receives Effective Floor Level 1 and Tier A."""
    queue = rank_waiting_queue(seed_df)
    a135 = next(p for p in queue if p["patient_token"] == "A135")

    assert a135["initial_triage_level"] == 1
    assert a135["protocol_floor_level"] == 2
    assert a135["effective_safety_floor"] == 1
    assert a135["effective_safety_floor_source"] == "CLINICIAN_TRIAGE"
    assert a135["queue_tier_code"] == TIER_A_CODE
    assert a135["priority_rank"] == 1


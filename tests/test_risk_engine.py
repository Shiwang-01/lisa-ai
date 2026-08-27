import os
import pandas as pd
import pytest

from lisa.protocol_floor import evaluate_protocol_floor
from lisa.risk_engine import evaluate_risk_of_wait, RISK_BREACH_THRESHOLD

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "seed_patients.csv")


@pytest.fixture
def seed_df():
    return pd.read_csv(DATA_PATH)


def test_scores_bounded_0_to_100(seed_df):
    """Test 1: Output scores always stay between 0 and 100 across entire cohort."""
    for _, patient in seed_df.iterrows():
        floor = evaluate_protocol_floor(patient)
        res = evaluate_risk_of_wait(patient, floor)
        for key in ["current_risk", "risk_30_min", "risk_60_min", "risk_120_min", "confidence"]:
            assert 0 <= res[key] <= 100, f"{key} out of bounds for {patient['patient_token']}: {res[key]}"


def test_future_risk_monotonic(seed_df):
    """Test 2: Future risk is monotonic non-decreasing: current <= 30 <= 60 <= 120."""
    for _, patient in seed_df.iterrows():
        floor = evaluate_protocol_floor(patient)
        res = evaluate_risk_of_wait(patient, floor)
        assert res["current_risk"] <= res["risk_30_min"] <= res["risk_60_min"] <= res["risk_120_min"], (
            f"Monotonicity violated for {patient['patient_token']}: "
            f"{res['current_risk']} <= {res['risk_30_min']} <= {res['risk_60_min']} <= {res['risk_120_min']}"
        )


def test_deterministic_identical_output(seed_df):
    """Test 3: Same patient input returns identical output every time."""
    patient = seed_df.iloc[0]
    floor = evaluate_protocol_floor(patient)
    res1 = evaluate_risk_of_wait(patient, floor)
    res2 = evaluate_risk_of_wait(patient, floor)
    assert res1 == res2


def test_token_independent():
    """Test 4: Function does not depend on patient_token."""
    patient_a = {
        "patient_token": "CUSTOM_999",
        "age": 32,
        "sex": "Male",
        "complaint_text": "Severe breathlessness, wheezing",
        "heart_rate": 118,
        "respiratory_rate": 30,
        "systolic_bp": 134,
        "diastolic_bp": 86,
        "spo2": 90,
        "temperature": 37.1,
        "pain_score": 4,
        "mental_status": "Alert",
        "visible_distress": "Moderate",
        "known_history": "Bronchial Asthma, Allergies",
        "prior_record_available": "Yes",
        "pregnancy_status": "Not Applicable",
        "arrival_minutes_ago": 25,
        "initial_triage_level": 2,
        "resource_need": "Nebulization, IV steroids, continuous monitoring",
        "case_notes": "Acute severe asthma exacerbation, speaking in broken sentences"
    }
    patient_b = dict(patient_a)
    del patient_b["patient_token"]

    floor_a = evaluate_protocol_floor(patient_a)
    floor_b = evaluate_protocol_floor(patient_b)

    res_a = evaluate_risk_of_wait(patient_a, floor_a)
    res_b = evaluate_risk_of_wait(patient_b, floor_b)
    assert res_a == res_b


def test_a124_higher_risk_than_a127(seed_df):
    """Test 5: A124 (respiratory) has higher Current Risk than A127 (ankle sprain)."""
    p124 = seed_df[seed_df["patient_token"] == "A124"].iloc[0]
    p127 = seed_df[seed_df["patient_token"] == "A127"].iloc[0]

    r124 = evaluate_risk_of_wait(p124, evaluate_protocol_floor(p124))
    r127 = evaluate_risk_of_wait(p127, evaluate_protocol_floor(p127))

    assert r124["current_risk"] > r127["current_risk"]


def test_a129_higher_risk_than_a141(seed_df):
    """Test 6: A129 (confusion+hypotension+fever) has higher Current Risk than A141 (knee injury)."""
    p129 = seed_df[seed_df["patient_token"] == "A129"].iloc[0]
    p141 = seed_df[seed_df["patient_token"] == "A141"].iloc[0]

    r129 = evaluate_risk_of_wait(p129, evaluate_protocol_floor(p129))
    r141 = evaluate_risk_of_wait(p141, evaluate_protocol_floor(p141))

    assert r129["current_risk"] > r141["current_risk"]


def test_a125_lower_confidence_than_a127(seed_df):
    """Test 7: A125 (ambiguous 'gas/sweating') has lower confidence than A127 (clear ankle injury)."""
    p125 = seed_df[seed_df["patient_token"] == "A125"].iloc[0]
    p127 = seed_df[seed_df["patient_token"] == "A127"].iloc[0]

    r125 = evaluate_risk_of_wait(p125, evaluate_protocol_floor(p125))
    r127 = evaluate_risk_of_wait(p127, evaluate_protocol_floor(p127))

    assert r125["confidence"] < r127["confidence"]


def test_a132_lower_confidence_than_a127(seed_df):
    """Test 8: A132 (vague weakness + zero history) has lower confidence than A127."""
    p132 = seed_df[seed_df["patient_token"] == "A132"].iloc[0]
    p127 = seed_df[seed_df["patient_token"] == "A127"].iloc[0]

    r132 = evaluate_risk_of_wait(p132, evaluate_protocol_floor(p132))
    r127 = evaluate_risk_of_wait(p127, evaluate_protocol_floor(p127))

    assert r132["confidence"] < r127["confidence"]


def test_low_confidence_never_reduces_urgency_or_delays_recheck():
    """Test 9: Low confidence does NOT reduce risk or prolong reassessment intervals."""
    base_patient = {
        "age": 45,
        "complaint_text": "Abdominal pain",
        "heart_rate": 100,
        "respiratory_rate": 20,
        "systolic_bp": 120,
        "spo2": 97,
        "temperature": 37.0,
        "pain_score": 5,
        "mental_status": "Alert",
        "visible_distress": "Moderate",
        "known_history": "Hypertension",
        "prior_record_available": "Yes"
    }
    unconfirmed_patient = dict(base_patient)
    unconfirmed_patient["prior_record_available"] = "No"
    unconfirmed_patient["known_history"] = "Unknown"

    r_base = evaluate_risk_of_wait(base_patient)
    r_unconfirmed = evaluate_risk_of_wait(unconfirmed_patient)

    # Confidence must be lower
    assert r_unconfirmed["confidence"] < r_base["confidence"]
    # Risk at 60 min must not be reduced
    assert r_unconfirmed["risk_60_min"] >= r_base["risk_60_min"]
    # Reassessment interval must not be lengthened
    assert r_unconfirmed["recheck_due_min"] <= r_base["recheck_due_min"]


def test_a127_longer_reassessment_than_a124(seed_df):
    """Test 10: A127 (low acuity ankle) receives longer reassessment interval than A124 (severe resp)."""
    p124 = seed_df[seed_df["patient_token"] == "A124"].iloc[0]
    p127 = seed_df[seed_df["patient_token"] == "A127"].iloc[0]

    r124 = evaluate_risk_of_wait(p124, evaluate_protocol_floor(p124))
    r127 = evaluate_risk_of_wait(p127, evaluate_protocol_floor(p127))

    assert r127["recheck_due_min"] > r124["recheck_due_min"]


def test_protocol_floor_level_2_contributes_to_concern():
    """Test 11: Protocol-floor Level 2 contributes to concern."""
    patient = {
        "age": 30,
        "complaint_text": "Minor symptom",
        "spo2": 98,
        "respiratory_rate": 16,
        "heart_rate": 75,
        "systolic_bp": 120,
        "temperature": 37.0,
        "mental_status": "Alert",
        "visible_distress": "Mild",
        "known_history": "None",
        "prior_record_available": "Yes"
    }
    floor_none = {"triggered": False, "floor_level": None, "rule_ids": [], "reasons": []}
    floor_l2 = {"triggered": True, "floor_level": 2, "rule_ids": ["GF-BLEED-01"], "reasons": ["Active bleeding"]}

    r_none = evaluate_risk_of_wait(patient, floor_none)
    r_l2 = evaluate_risk_of_wait(patient, floor_l2)

    assert r_l2["current_risk"] > r_none["current_risk"]
    assert "RW-GUARDRAIL-L2" in r_l2["explanation_codes"]


def test_low_acuity_stable_not_critical_solely_due_to_age_or_pain():
    """Test 12: A low-acuity stable patient does not become critical solely because of age or pain."""
    elderly_pain_patient = {
        "age": 82,
        "complaint_text": "Twisted wrist while reading, isolated soreness",
        "heart_rate": 72,
        "respiratory_rate": 15,
        "systolic_bp": 125,
        "spo2": 98,
        "temperature": 36.8,
        "pain_score": 9,
        "mental_status": "Alert",
        "visible_distress": "Mild",
        "known_history": "Osteoarthritis",
        "prior_record_available": "Yes"
    }
    res = evaluate_risk_of_wait(elderly_pain_patient, {"triggered": False, "floor_level": None})
    assert res["risk_band"] != "Critical"
    assert res["current_risk"] < RISK_BREACH_THRESHOLD


def test_time_to_breach_zero_when_current_risk_above_threshold():
    """Test 13: time_to_breach = 0 when Current Risk is already above breach threshold."""
    critical_patient = {
        "age": 75,
        "complaint_text": "Sudden acute collapse, unresponsive, hypotension",
        "heart_rate": 140,
        "respiratory_rate": 35,
        "systolic_bp": 70,
        "spo2": 85,
        "temperature": 38.8,
        "pain_score": 0,
        "mental_status": "Unresponsive",
        "visible_distress": "Severe",
        "known_history": "Multiple comorbidities",
        "prior_record_available": "Yes"
    }
    floor_l1 = {"triggered": True, "floor_level": 1, "rule_ids": ["GF-CRITICAL-01"], "reasons": ["Unresponsive"]}
    res = evaluate_risk_of_wait(critical_patient, floor_l1)
    assert res["current_risk"] >= RISK_BREACH_THRESHOLD
    assert res["time_to_breach_min"] == 0


def test_multiple_missing_elements_reduce_confidence():
    """Test 14: Multiple missing data elements reduce confidence progressively."""
    complete = {
        "age": 40,
        "complaint_text": "Right knee pain",
        "heart_rate": 75,
        "respiratory_rate": 16,
        "systolic_bp": 120,
        "spo2": 99,
        "temperature": 37.0,
        "mental_status": "Alert",
        "prior_record_available": "Yes",
        "known_history": "None"
    }
    missing_one = dict(complete)
    missing_one["spo2"] = None

    missing_multiple = dict(complete)
    missing_multiple["spo2"] = None
    missing_multiple["systolic_bp"] = None
    missing_multiple["prior_record_available"] = "No"

    r0 = evaluate_risk_of_wait(complete)
    r1 = evaluate_risk_of_wait(missing_one)
    r2 = evaluate_risk_of_wait(missing_multiple)

    assert r0["confidence"] > r1["confidence"] > r2["confidence"]


def test_explanation_codes_populated(seed_df):
    """Test 15: Risk output includes explanation codes."""
    for _, patient in seed_df.iterrows():
        floor = evaluate_protocol_floor(patient)
        res = evaluate_risk_of_wait(patient, floor)
        assert isinstance(res["explanation_codes"], list)
        assert len(res["explanation_codes"]) > 0
        assert isinstance(res["risk_factors"], list)
        assert isinstance(res["uncertainty_factors"], list)


def test_a125_non_diagnostic_language(seed_df):
    """Test 16: Human-readable explanations for A125 do NOT infer diagnoses (no ACS, angina, infarction, etc.)."""
    p125 = seed_df[seed_df["patient_token"] == "A125"].iloc[0]
    floor = evaluate_protocol_floor(p125)
    res = evaluate_risk_of_wait(p125, floor)

    all_explanations = " ".join(res["risk_factors"] + res["uncertainty_factors"]).lower()

    prohibited_terms = [
        "acs",
        "angina",
        "myocardial infarction",
        "heart attack",
        "ischemia",
        "sepsis",
        "stroke diagnosis",
        "anaphylaxis diagnosis"
    ]
    for term in prohibited_terms:
        assert term not in all_explanations, f"Prohibited diagnosis/disease inference term found: '{term}' in '{all_explanations}'"

    # Verify presence of neutral observable descriptions
    assert any("ambiguous" in f.lower() for f in res["risk_factors"] + res["uncertainty_factors"])
    assert any("sweating" in f.lower() for f in res["risk_factors"])


def test_a135_protocol_floor_and_reassessment_priority(seed_df):
    """Test 17: A135 retains Level 2 Protocol Floor and urgent reassessment (5 min) without artificial score inflation."""
    p135 = seed_df[seed_df["patient_token"] == "A135"].iloc[0]
    floor = evaluate_protocol_floor(p135)
    res = evaluate_risk_of_wait(p135, floor)

    assert floor["triggered"] is True
    assert floor["floor_level"] == 2
    assert res["recheck_due_min"] == 5
    # Numerical Current Risk reflects physiology, not artificially set >= 75
    assert res["current_risk"] < RISK_BREACH_THRESHOLD
    assert res["time_to_breach_min"] is not None and res["time_to_breach_min"] > 0

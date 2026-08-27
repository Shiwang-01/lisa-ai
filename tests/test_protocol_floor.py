import os
import pandas as pd
import pytest

from lisa.protocol_floor import evaluate_protocol_floor

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "seed_patients.csv")


@pytest.fixture
def seed_df():
    return pd.read_csv(DATA_PATH)


def test_a124_respiratory_level_2(seed_df):
    patient = seed_df[seed_df["patient_token"] == "A124"].iloc[0]
    res = evaluate_protocol_floor(patient)
    assert res["triggered"] is True
    assert res["floor_level"] == 2
    assert "GF-RESP-01" in res["rule_ids"]
    assert any("respiratory" in r.lower() or "oxygen" in r.lower() for r in res["reasons"])


def test_a126_pediatric_level_2(seed_df):
    patient = seed_df[seed_df["patient_token"] == "A126"].iloc[0]
    res = evaluate_protocol_floor(patient)
    assert res["triggered"] is True
    assert res["floor_level"] == 2
    assert "GF-PEDS-01" in res["rule_ids"]
    assert any("pediatric" in r.lower() for r in res["reasons"])


def test_a130_pregnancy_bleeding_level_2(seed_df):
    patient = seed_df[seed_df["patient_token"] == "A130"].iloc[0]
    res = evaluate_protocol_floor(patient)
    assert res["triggered"] is True
    assert res["floor_level"] == 2
    assert "GF-PREG-01" in res["rule_ids"]
    assert any("pregnancy" in r.lower() for r in res["reasons"])


def test_a135_stroke_level_2(seed_df):
    patient = seed_df[seed_df["patient_token"] == "A135"].iloc[0]
    res = evaluate_protocol_floor(patient)
    assert res["triggered"] is True
    assert res["floor_level"] == 2
    assert "GF-STROKE-01" in res["rule_ids"]
    assert any("stroke" in r.lower() for r in res["reasons"])


def test_a142_airway_allergy_level_2(seed_df):
    patient = seed_df[seed_df["patient_token"] == "A142"].iloc[0]
    res = evaluate_protocol_floor(patient)
    assert res["triggered"] is True
    assert res["floor_level"] == 2
    assert "GF-AIRWAY-01" in res["rule_ids"]
    assert any("airway" in r.lower() for r in res["reasons"])


def test_a127_low_acuity_control_no_floor(seed_df):
    patient = seed_df[seed_df["patient_token"] == "A127"].iloc[0]
    res = evaluate_protocol_floor(patient)
    assert res["triggered"] is False
    assert res["floor_level"] is None
    assert len(res["reasons"]) == 0
    assert len(res["rule_ids"]) == 0


def test_a141_low_acuity_control_no_floor(seed_df):
    patient = seed_df[seed_df["patient_token"] == "A141"].iloc[0]
    res = evaluate_protocol_floor(patient)
    assert res["triggered"] is False
    assert res["floor_level"] is None
    assert len(res["reasons"]) == 0
    assert len(res["rule_ids"]) == 0


def test_multiple_triggered_rules_return_multiple_reasons(seed_df):
    # A129 (Hypotension + Confusion + Fever) triggers both Altered Mental Status and Shock rules
    patient = seed_df[seed_df["patient_token"] == "A129"].iloc[0]
    res = evaluate_protocol_floor(patient)
    assert res["triggered"] is True
    assert res["floor_level"] == 2
    assert len(res["rule_ids"]) >= 2
    assert len(res["reasons"]) >= 2
    assert "GF-MENTAL-01" in res["rule_ids"]
    assert "GF-SHOCK-01" in res["rule_ids"]


def test_most_urgent_rule_wins_level_1_over_level_2():
    # Synthetic patient with both Level 2 condition (respiratory distress) and Level 1 (unresponsive)
    custom_patient = {
        "age": 45,
        "spo2": 88,
        "respiratory_rate": 32,
        "mental_status": "Unresponsive",
        "complaint_text": "Severe breathlessness, collapsed, unresponsive",
        "visible_distress": "Severe",
        "case_notes": "Immediate resuscitation needed",
        "pregnancy_status": "Not Applicable",
        "systolic_bp": 85,
        "temperature": 37.0
    }
    res = evaluate_protocol_floor(custom_patient)
    assert res["triggered"] is True
    assert res["floor_level"] == 1
    assert "GF-CRITICAL-01" in res["rule_ids"]
    assert "GF-RESP-01" in res["rule_ids"]


def test_function_independent_of_patient_token():
    # Ensure patient_token field is completely irrelevant for decision
    custom_patient_without_token = {
        "age": 28,
        "sex": "Female",
        "complaint_text": "Severe acute right-sided facial droop and slurred speech",
        "mental_status": "Alert",
        "visible_distress": "Moderate",
        "case_notes": "Stroke protocol alert",
        "pregnancy_status": "Not Applicable",
        "spo2": 98,
        "systolic_bp": 150,
        "diastolic_bp": 95,
        "heart_rate": 84,
        "respiratory_rate": 18,
        "temperature": 36.8
    }
    res = evaluate_protocol_floor(custom_patient_without_token)
    assert res["triggered"] is True
    assert res["floor_level"] == 2
    assert "GF-STROKE-01" in res["rule_ids"]

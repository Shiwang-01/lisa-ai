"""LISA.ai — FastAPI Integration Tests (Milestone 11A)

Verifies REST API behavior, patient data consistency, surge invariance,
capacity bounds, safety-floor override protection, and audit trails.
"""

import pytest
from fastapi.testclient import TestClient

from webapp import app, audit_manager
from lisa.surge_simulator import get_operational_mode, MODE_NORMAL, MODE_SURGE_3X
from lisa.protocol_floor import evaluate_protocol_floor
from lisa.risk_engine import evaluate_risk_of_wait
from lisa.sequencer import rank_waiting_queue
from lisa.allocator import allocate_available_beds
from lisa.governance import get_governance_summary


@pytest.fixture(autouse=True)
def reset_audit_state():
    """Ensures audit trail is empty before and after each test."""
    audit_manager.clear()
    yield
    audit_manager.clear()


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


def test_status_endpoint(client):
    """1. GET /api/status returns 200 and expected metadata."""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["application"] == "LISA.ai"
    assert data["status"] == "ok"
    assert data["prototype"] is True
    assert data["clinical_use"] is False
    assert "NORMAL" in data["supported_modes"]
    assert "SURGE_3X" in data["supported_modes"]


def test_summary_normal_and_surge(client):
    """2-4. Summary endpoint verification for Normal and Surge modes."""
    # Normal Mode
    res_norm = client.get("/api/summary?mode=NORMAL")
    assert res_norm.status_code == 200
    d_norm = res_norm.json()
    assert d_norm["patient_count"] == 20
    assert d_norm["bed_count"] == 8
    assert d_norm["patients_per_bed"] == 2.5
    assert d_norm["patients_per_triage_nurse"] == 20.0
    assert d_norm["allocated_count"] <= 8

    # Surge Mode
    res_surge = client.get("/api/summary?mode=SURGE_3X")
    assert res_surge.status_code == 200
    d_surge = res_surge.json()
    assert d_surge["patient_count"] == 60
    assert d_surge["bed_count"] == 8
    assert d_surge["patients_per_bed"] == 7.5
    assert d_surge["patients_per_triage_nurse"] == 60.0
    assert d_surge["allocated_count"] <= 8


def test_queue_endpoint_cardinality_and_ranks(client):
    """5-7. Queue endpoint returns unique tokens and valid continuous ranks."""
    # Normal Mode
    res_norm = client.get("/api/queue?mode=NORMAL")
    assert res_norm.status_code == 200
    q_norm = res_norm.json()
    assert len(q_norm) == 20
    tokens_norm = [p["patient_token"] for p in q_norm]
    assert len(set(tokens_norm)) == 20
    ranks_norm = [p["priority_rank"] for p in q_norm]
    assert ranks_norm == list(range(1, 21))

    # Surge Mode
    res_surge = client.get("/api/queue?mode=SURGE_3X")
    assert res_surge.status_code == 200
    q_surge = res_surge.json()
    assert len(q_surge) == 60
    tokens_surge = [p["patient_token"] for p in q_surge]
    assert len(set(tokens_surge)) == 60
    ranks_surge = [p["priority_rank"] for p in q_surge]
    assert ranks_surge == list(range(1, 61))


def test_patient_a125_matches_backend(client):
    """8-9. Patient A125 API response matches direct Python backend engine outputs."""
    res = client.get("/api/patient/A125?mode=NORMAL")
    assert res.status_code == 200
    api_data = res.json()

    # Compare against direct backend computation
    mode_ctx = get_operational_mode(MODE_NORMAL)
    patients_df = mode_ctx["patients"]
    row_a125 = patients_df[patients_df["patient_token"] == "A125"].iloc[0]

    f_res = evaluate_protocol_floor(row_a125)
    r_res = evaluate_risk_of_wait(row_a125, f_res)
    ranked = rank_waiting_queue(patients_df)
    ranked_a125 = next(p for p in ranked if p["patient_token"] == "A125")

    # Patient demographics & vitals
    assert api_data["patient"]["patient_token"] == "A125"
    assert api_data["patient"]["age"] == int(row_a125["age"])
    assert api_data["patient"]["sex"] == str(row_a125["sex"])
    assert api_data["patient"]["initial_triage_level"] == int(row_a125["initial_triage_level"])

    # Risk-of-Wait trajectory
    assert api_data["risk_of_wait"]["current_risk"] == r_res["current_risk"]
    assert api_data["risk_of_wait"]["risk_30_min"] == r_res["risk_30_min"]
    assert api_data["risk_of_wait"]["risk_60_min"] == r_res["risk_60_min"]
    assert api_data["risk_of_wait"]["risk_120_min"] == r_res["risk_120_min"]
    assert api_data["risk_of_wait"]["confidence"] == r_res["confidence"]
    assert api_data["risk_of_wait"]["recheck_due_min"] == r_res["recheck_due_min"]

    # Queue sequencing
    assert api_data["queue"]["priority_rank"] == ranked_a125["priority_rank"]
    assert api_data["queue"]["queue_tier"] == ranked_a125["queue_tier"]
    assert api_data["queue"]["sequence_score"] == ranked_a125["sequence_score"]


def test_patient_a135_safety_floor_matches_backend(client):
    """10. Patient A135 Clinician Level 1 safety floor dominates Protocol Level 2."""
    res = client.get("/api/patient/A135?mode=NORMAL")
    assert res.status_code == 200
    api_data = res.json()

    # Compare against direct backend computation
    mode_ctx = get_operational_mode(MODE_NORMAL)
    patients_df = mode_ctx["patients"]
    row_a135 = patients_df[patients_df["patient_token"] == "A135"].iloc[0]

    f_res = evaluate_protocol_floor(row_a135)
    ranked = rank_waiting_queue(patients_df)
    ranked_a135 = next(p for p in ranked if p["patient_token"] == "A135")

    assert api_data["guardrails"]["initial_triage_level"] == 1
    assert api_data["guardrails"]["protocol_floor_level"] == 2
    assert api_data["guardrails"]["effective_safety_floor"] == 1
    assert api_data["guardrails"]["has_hard_floor"] is True
    assert api_data["queue"]["queue_tier_code"] == "Tier A"
    assert api_data["queue"]["priority_rank"] == 1
    assert api_data["queue"]["priority_rank"] == ranked_a135["priority_rank"]


def test_surge_invariance_for_original_patients(client):
    """11. Original patients A124-A143 have identical clinical Risk-of-Wait outputs between Normal and Surge."""
    mode_norm = get_operational_mode(MODE_NORMAL)
    mode_surge = get_operational_mode(MODE_SURGE_3X)

    orig_tokens = [f"A{i}" for i in range(124, 144)]

    for tok in orig_tokens:
        res_n = client.get(f"/api/patient/{tok}?mode=NORMAL")
        res_s = client.get(f"/api/patient/{tok}?mode=SURGE_3X")

        assert res_n.status_code == 200
        assert res_s.status_code == 200

        data_n = res_n.json()
        data_s = res_s.json()

        # Clinical Risk-of-Wait invariance
        assert data_n["risk_of_wait"]["current_risk"] == data_s["risk_of_wait"]["current_risk"]
        assert data_n["risk_of_wait"]["risk_30_min"] == data_s["risk_of_wait"]["risk_30_min"]
        assert data_n["risk_of_wait"]["risk_60_min"] == data_s["risk_of_wait"]["risk_60_min"]
        assert data_n["risk_of_wait"]["risk_120_min"] == data_s["risk_of_wait"]["risk_120_min"]
        assert data_n["risk_of_wait"]["confidence"] == data_s["risk_of_wait"]["confidence"]
        assert data_n["risk_of_wait"]["recheck_due_min"] == data_s["risk_of_wait"]["recheck_due_min"]

        # Safety floor invariance
        assert data_n["guardrails"]["effective_safety_floor"] == data_s["guardrails"]["effective_safety_floor"]


def test_allocation_bounds_and_uniqueness(client):
    """12-13. Resource allocation never exceeds 8 beds and contains no duplicate bed assignments."""
    for m in ["NORMAL", "SURGE_3X"]:
        res = client.get(f"/api/allocation?mode={m}")
        assert res.status_code == 200
        data = res.json()

        beds = data["beds"]
        assert len(beds) == 8
        bed_ids = [b["bed_id"] for b in beds]
        assert sorted(bed_ids) == ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08"]

        allocations = data["allocations"]
        assert len(allocations) <= 8

        assigned_beds = [a["bed_id"] for a in allocations if a.get("bed_id")]
        assert len(assigned_beds) == len(set(assigned_beds))


def test_action_accept_creates_audit_event(client):
    """14. A125 ACCEPT action successfully creates an audit log entry."""
    payload = {
        "patient_token": "A125",
        "mode": "NORMAL",
        "user_role": "TRIAGE_NURSE_01"
    }
    res = client.post("/api/actions/accept", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["action"] == "ACCEPT"
    assert data["event"]["patient_token"] == "A125"

    # Verify event in GET /api/audit
    res_audit = client.get("/api/audit")
    assert res_audit.status_code == 200
    audit_data = res_audit.json()
    assert audit_data["count"] == 1
    assert audit_data["events"][0]["patient_token"] == "A125"
    assert audit_data["events"][0]["action"] == "ACCEPT"


def test_action_override_success(client):
    """15. A125 Override Tier C -> Tier B with CLINICAL_APPEARANCE succeeds."""
    payload = {
        "patient_token": "A125",
        "target_tier": "Tier B",
        "reason": "CLINICAL_APPEARANCE",
        "note": "Patient appears more fatigued than intake indicates.",
        "mode": "NORMAL",
        "user_role": "TRIAGE_NURSE_01"
    }
    res = client.post("/api/actions/override", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["action"] == "OVERRIDE"
    assert data["event"]["clinician_selected_tier"] == "Tier B"
    assert data["event"]["override_reason"] == "CLINICAL_APPEARANCE"


def test_action_override_safety_floor_blocking(client):
    """16-17. Safety floor violations are blocked with HTTP 409 Conflict."""
    # A135: Effective Safety Floor Level 1 -> Cannot downgrade to Tier B
    payload_a135 = {
        "patient_token": "A135",
        "target_tier": "Tier B",
        "reason": "CLINICAL_APPEARANCE",
        "mode": "NORMAL"
    }
    res_135 = client.post("/api/actions/override", json=payload_a135)
    assert res_135.status_code == 409
    assert "Override blocked" in res_135.json()["detail"]

    # A124: Effective Safety Floor Level 2 -> Cannot downgrade to Tier C
    payload_a124 = {
        "patient_token": "A124",
        "target_tier": "Tier C",
        "reason": "CLINICAL_APPEARANCE",
        "mode": "NORMAL"
    }
    res_124 = client.post("/api/actions/override", json=payload_a124)
    assert res_124.status_code == 409
    assert "Override blocked" in res_124.json()["detail"]


def test_action_escalate_and_audit_reset(client):
    """18. Escalate action and audit reset endpoint."""
    # Escalate A125 (Tier C -> Tier B)
    res_esc = client.post("/api/actions/escalate", json={"patient_token": "A125", "mode": "NORMAL"})
    assert res_esc.status_code == 200
    data_esc = res_esc.json()
    assert data_esc["status"] == "success"
    assert data_esc["action"] == "ESCALATE"
    assert data_esc["event"]["clinician_selected_tier"] == "Tier B"

    # Reset audit trail
    res_reset = client.post("/api/audit/reset")
    assert res_reset.status_code == 200
    assert res_reset.json()["status"] == "reset"

    # Verify audit is empty
    res_audit = client.get("/api/audit")
    assert res_audit.json()["count"] == 0
    assert res_audit.json()["events"] == []


def test_governance_and_comparison_endpoints(client):
    """19-20. Governance and Comparison endpoints return accurate simulation metadata."""
    # Governance
    res_gov = client.get("/api/governance")
    assert res_gov.status_code == 200
    expected_gov = get_governance_summary()
    assert res_gov.json()["clinical_safety_position"]["statement"] == expected_gov["clinical_safety_position"]["statement"]
    assert res_gov.json()["implemented_prototype_controls"] == expected_gov["implemented_prototype_controls"]

    # Comparison
    res_comp = client.get("/api/comparison?mode=NORMAL")
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert comp_data["simulation_only"] is True
    assert comp_data["clinical_efficacy_evidence"] is False
    assert "comparison" in comp_data
    assert "static_baseline" in comp_data["comparison"]
    assert "lisa" in comp_data["comparison"]
    assert "differences" in comp_data["comparison"]


def test_error_handling(client):
    """Invalid modes, unknown patients, and invalid override reasons return appropriate HTTP errors."""
    # Invalid mode
    res_bad_mode = client.get("/api/summary?mode=INVALID_MODE")
    assert res_bad_mode.status_code == 400

    # Nonexistent patient
    res_bad_pat = client.get("/api/patient/NONEXISTENT_999?mode=NORMAL")
    assert res_bad_pat.status_code == 404

    # Invalid override reason
    res_bad_reason = client.post(
        "/api/actions/override",
        json={
            "patient_token": "A125",
            "target_tier": "Tier B",
            "reason": "INVALID_REASON_CODE",
            "mode": "NORMAL"
        }
    )
    assert res_bad_reason.status_code == 400

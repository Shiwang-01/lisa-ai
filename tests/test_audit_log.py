import os
import pandas as pd
import pytest

from lisa.surge_simulator import load_normal_cohort
from lisa.sequencer import rank_waiting_queue, TIER_A_CODE, TIER_B_CODE, TIER_C_CODE, TIER_D_CODE, TIER_E_CODE
from lisa.allocator import load_beds_inventory, allocate_available_beds
from lisa.audit_log import (
    create_audit_event,
    validate_clinician_override,
    calculate_escalated_tier,
    AuditTrailManager,
    ACTION_ACCEPT,
    ACTION_OVERRIDE,
    ACTION_ESCALATE,
    MODEL_VERSION,
    RULE_VERSION,
    SEQUENCER_VERSION,
    DEFAULT_USER_ROLE
)


@pytest.fixture
def normal_pipeline():
    df = load_normal_cohort()
    beds = load_beds_inventory()
    queue = rank_waiting_queue(df)
    alloc = allocate_available_beds(queue, beds)
    queue_map = {p["patient_token"]: p for p in queue}
    alloc_map = {p["patient_token"]: p for p in alloc["patient_allocations"]}
    return {
        "df": df,
        "queue_map": queue_map,
        "alloc_map": alloc_map
    }


def test_audit_event_structure_and_uniqueness(normal_pipeline):
    """Tests 1, 2, 3, 4, 5, 6, 20, 21: Audit event contains all required fields, valid UUID, timestamp, versions."""
    p_rank = normal_pipeline["queue_map"]["A124"]
    p_alloc = normal_pipeline["alloc_map"]["A124"]

    evt1 = create_audit_event("A124", ACTION_ACCEPT, p_rank, p_alloc)
    evt2 = create_audit_event("A124", ACTION_ACCEPT, p_rank, p_alloc)

    assert evt1["event_id"] != evt2["event_id"]
    assert "T" in evt1["timestamp"]
    assert evt1["patient_token"] == "A124"
    assert evt1["user_role"] == DEFAULT_USER_ROLE
    assert evt1["system_queue_tier"] == p_rank["queue_tier_code"]
    assert evt1["system_sequence_score"] == p_rank["sequence_score"]
    assert evt1["current_risk"] == p_rank["current_risk"]
    assert evt1["risk_60_min"] == p_rank["risk_60_min"]
    assert evt1["confidence"] == p_rank["confidence"]
    assert evt1["model_version"] == MODEL_VERSION
    assert evt1["rule_version"] == RULE_VERSION
    assert evt1["sequencer_version"] == SEQUENCER_VERSION

    # Privacy check: no name or national ID fields
    forbidden_keys = ["name", "patient_name", "ssn", "aadhaar", "phone", "address"]
    for k in evt1.keys():
        assert k not in forbidden_keys


def test_accept_event_does_not_require_reason(normal_pipeline):
    """Test 7: ACCEPT event does not require an override reason."""
    p_rank = normal_pipeline["queue_map"]["A127"]
    p_alloc = normal_pipeline["alloc_map"]["A127"]

    evt = create_audit_event("A127", ACTION_ACCEPT, p_rank, p_alloc)
    assert evt["action"] == ACTION_ACCEPT
    assert evt["override_reason"] is None
    assert evt["clinician_selected_tier"] == p_rank["queue_tier_code"]


def test_override_requires_reason(normal_pipeline):
    """Test 8: OVERRIDE requires a non-empty clinical reason."""
    p_rank = normal_pipeline["queue_map"]["A127"]
    p_alloc = normal_pipeline["alloc_map"]["A127"]

    # Missing reason raises ValueError
    with pytest.raises(ValueError, match="reason"):
        create_audit_event(
            "A127",
            ACTION_OVERRIDE,
            p_rank,
            p_alloc,
            clinician_selected_tier="Tier C",
            override_reason=""
        )


def test_override_preserves_system_recommendation(normal_pipeline):
    """Test 9: OVERRIDE preserves the original system recommendation alongside the clinician selection."""
    p_rank = normal_pipeline["queue_map"]["A125"]  # System Tier C
    p_alloc = normal_pipeline["alloc_map"]["A125"]

    evt = create_audit_event(
        "A125",
        ACTION_OVERRIDE,
        p_rank,
        p_alloc,
        clinician_selected_tier="Tier B",
        override_reason="CLINICAL_APPEARANCE",
        override_note="Appears more unwell than intake suggests"
    )

    assert evt["system_queue_tier"] == TIER_C_CODE
    assert evt["clinician_selected_tier"] == TIER_B_CODE
    assert evt["override_reason"] == "CLINICAL_APPEARANCE"
    assert evt["override_note"] == "Appears more unwell than intake suggests"


def test_level_1_safety_floor_blocks_downgrade(normal_pipeline):
    """Test 10 & Demo Case 3: Level 1 effective safety floor blocks downgrade below Tier A (A135)."""
    p_rank = normal_pipeline["queue_map"]["A135"]  # Level 1 safety floor, Tier A
    p_alloc = normal_pipeline["alloc_map"]["A135"]

    assert p_rank["effective_safety_floor"] == 1

    # Attempt override A -> B must fail
    is_valid, err = validate_clinician_override(p_rank["effective_safety_floor"], "Tier B", "CLINICIAN_JUDGMENT")
    assert not is_valid
    assert "Level 1" in err

    with pytest.raises(ValueError, match="safety floor"):
        create_audit_event(
            "A135",
            ACTION_OVERRIDE,
            p_rank,
            p_alloc,
            clinician_selected_tier="Tier B",
            override_reason="CLINICIAN_JUDGMENT"
        )


def test_level_2_safety_floor_blocks_downgrade(normal_pipeline):
    """Test 11 & Demo Case 4: Level 2 effective safety floor blocks downgrade below Tier B (A124)."""
    p_rank = normal_pipeline["queue_map"]["A124"]  # Level 2 safety floor, Tier B
    p_alloc = normal_pipeline["alloc_map"]["A124"]

    assert p_rank["effective_safety_floor"] == 2

    # Attempt override B -> C must fail
    is_valid, err = validate_clinician_override(p_rank["effective_safety_floor"], "Tier C", "CLINICAL_APPEARANCE")
    assert not is_valid
    assert "Level 2" in err

    with pytest.raises(ValueError, match="safety floor"):
        create_audit_event(
            "A124",
            ACTION_OVERRIDE,
            p_rank,
            p_alloc,
            clinician_selected_tier="Tier C",
            override_reason="CLINICAL_APPEARANCE"
        )


def test_allowed_upward_override_succeeds(normal_pipeline):
    """Test 12 & Demo Case 1: Allowed upward override succeeds (A125 Tier C -> Tier B)."""
    p_rank = normal_pipeline["queue_map"]["A125"]  # Tier C, effective safety floor Level 4
    p_alloc = normal_pipeline["alloc_map"]["A125"]

    is_valid, err = validate_clinician_override(p_rank["effective_safety_floor"], "Tier B", "CLINICAL_APPEARANCE")
    assert is_valid
    assert err is None

    evt = create_audit_event(
        "A125",
        ACTION_OVERRIDE,
        p_rank,
        p_alloc,
        clinician_selected_tier="Tier B",
        override_reason="CLINICAL_APPEARANCE",
        override_note="Patient appears more unwell than structured intake suggests."
    )
    assert evt["clinician_selected_tier"] == "Tier B"
    assert evt["override_reason"] == "CLINICAL_APPEARANCE"


def test_escalate_one_step_behavior():
    """Tests 13 & 14: Escalation increases urgency by exactly one step and caps at Tier A."""
    assert calculate_escalated_tier("Tier E") == TIER_D_CODE
    assert calculate_escalated_tier("Tier D") == TIER_C_CODE
    assert calculate_escalated_tier("Tier C") == TIER_B_CODE
    assert calculate_escalated_tier("Tier B") == TIER_A_CODE
    assert calculate_escalated_tier("Tier A") == TIER_A_CODE


def test_escalate_demo_case_a127(normal_pipeline):
    """Demo Case 2: A127 (Tier E) escalated to Tier D."""
    p_rank = normal_pipeline["queue_map"]["A127"]  # System Tier E
    p_alloc = normal_pipeline["alloc_map"]["A127"]

    evt = create_audit_event("A127", ACTION_ESCALATE, p_rank, p_alloc)
    assert evt["action"] == ACTION_ESCALATE
    assert evt["system_queue_tier"] == TIER_E_CODE
    assert evt["clinician_selected_tier"] == TIER_D_CODE


def test_audit_manager_append_only(normal_pipeline):
    """Tests 15 & 16: Audit manager is strictly append-only and preserves all events."""
    mgr = AuditTrailManager()
    assert mgr.count() == 0

    p_rank_125 = normal_pipeline["queue_map"]["A125"]
    p_alloc_125 = normal_pipeline["alloc_map"]["A125"]

    evt1 = create_audit_event("A125", ACTION_ACCEPT, p_rank_125, p_alloc_125)
    evt2 = create_audit_event("A125", ACTION_OVERRIDE, p_rank_125, p_alloc_125, clinician_selected_tier="Tier B", override_reason="CLINICAL_JUDGMENT")
    evt3 = create_audit_event("A125", ACTION_ESCALATE, p_rank_125, p_alloc_125)

    mgr.log_event(evt1)
    mgr.log_event(evt2)
    mgr.log_event(evt3)

    assert mgr.count() == 3
    events = mgr.get_events()
    assert len(events) == 3
    assert [e["action"] for e in events] == [ACTION_ACCEPT, ACTION_OVERRIDE, ACTION_ESCALATE]

    # Check latest action lookup
    latest = mgr.get_latest_action_for_patient("A125")
    assert latest["action"] == ACTION_ESCALATE


def test_clinician_action_does_not_mutate_patient_clinical_facts(normal_pipeline):
    """Tests 17, 18, 19: Clinician actions never mutate risk scores, floors, or initial triage."""
    p_rank = normal_pipeline["queue_map"]["A125"]
    p_alloc = normal_pipeline["alloc_map"]["A125"]

    orig_risk = p_rank["current_risk"]
    orig_floor = p_rank["protocol_floor_level"]
    orig_init = p_rank["initial_triage_level"]

    evt = create_audit_event(
        "A125",
        ACTION_OVERRIDE,
        p_rank,
        p_alloc,
        clinician_selected_tier="Tier A",
        override_reason="PATIENT_DETERIORATION"
    )

    # Underlying patient record values remain untouched
    assert p_rank["current_risk"] == orig_risk
    assert p_rank["protocol_floor_level"] == orig_floor
    assert p_rank["initial_triage_level"] == orig_init


def test_reset_demo_actions_clears_events_only(normal_pipeline):
    """Check 2: Reset Demo Actions clears session audit events without modifying pipeline data."""
    mgr = AuditTrailManager()
    p_rank = normal_pipeline["queue_map"]["A125"]
    p_alloc = normal_pipeline["alloc_map"]["A125"]

    evt = create_audit_event("A125", ACTION_ACCEPT, p_rank, p_alloc)
    mgr.log_event(evt)
    assert mgr.count() == 1

    # Reset
    mgr.clear()
    assert mgr.count() == 0
    assert mgr.get_events() == []
    assert mgr.get_latest_action_for_patient("A125") is None

    # Underlying pipeline remains intact
    assert p_rank["queue_tier_code"] == TIER_C_CODE
    assert p_rank["current_risk"] == 35


def test_resource_context_derived_from_current_mode_allocation(normal_pipeline):
    """Check 3: system_resource_status, bed_id, and bed_type strictly reflect the passed allocation context."""
    p_rank = normal_pipeline["queue_map"]["A125"]

    # Context 1: Allocated to General Bed B06 in Normal Mode
    alloc_normal = {"allocation_status": "ALLOCATED", "bed_id": "B06", "bed_type": "General"}
    evt_normal = create_audit_event("A125", ACTION_ACCEPT, p_rank, alloc_normal, operational_mode="NORMAL")

    assert evt_normal["system_resource_status"] == "ALLOCATED"
    assert evt_normal["system_bed_id"] == "B06"
    assert evt_normal["system_bed_type"] == "General"
    assert evt_normal["operational_mode"] == "NORMAL"

    # Context 2: Unallocated WAITING_QUEUE in Surge Mode
    alloc_surge = {"allocation_status": "WAITING_QUEUE", "bed_id": None, "bed_type": None}
    evt_surge = create_audit_event("A125", ACTION_ACCEPT, p_rank, alloc_surge, operational_mode="SURGE_3X")

    assert evt_surge["system_resource_status"] == "WAITING_QUEUE"
    assert evt_surge["system_bed_id"] is None
    assert evt_surge["system_bed_type"] is None
    assert evt_surge["operational_mode"] == "SURGE_3X"


def test_a125_three_event_append_only_history(normal_pipeline):
    """Checks 5 & 6: A125 sequence: ACCEPT -> OVERRIDE C->B -> ESCALATE B->A preserves 3 separate events with latest state = Tier A."""
    mgr = AuditTrailManager()
    p_rank = normal_pipeline["queue_map"]["A125"]  # System Tier C
    p_alloc = normal_pipeline["alloc_map"]["A125"]

    # 1. ACCEPT
    evt1 = create_audit_event("A125", ACTION_ACCEPT, p_rank, p_alloc)
    mgr.log_event(evt1)

    # 2. OVERRIDE to Tier B
    evt2 = create_audit_event(
        "A125",
        ACTION_OVERRIDE,
        p_rank,
        p_alloc,
        clinician_selected_tier="Tier B",
        override_reason="CLINICAL_APPEARANCE",
        override_note="Patient appears more unwell than structured intake suggests."
    )
    mgr.log_event(evt2)

    # 3. ESCALATE (escalates from current active Tier B to Tier A)
    current_tier = mgr.get_latest_action_for_patient("A125")["clinician_selected_tier"]
    assert current_tier == "Tier B"
    evt3 = create_audit_event(
        "A125",
        ACTION_ESCALATE,
        p_rank,
        p_alloc,
        current_active_tier=current_tier
    )
    mgr.log_event(evt3)

    # Verify 3 distinct events
    events = mgr.get_events_for_patient("A125")
    assert len(events) == 3

    assert events[0]["action"] == ACTION_ACCEPT
    assert events[0]["clinician_selected_tier"] == "Tier C"

    assert events[1]["action"] == ACTION_OVERRIDE
    assert events[1]["clinician_selected_tier"] == "Tier B"
    assert events[1]["override_reason"] == "CLINICAL_APPEARANCE"

    assert events[2]["action"] == ACTION_ESCALATE
    assert events[2]["clinician_selected_tier"] == "Tier A"

    # Verify latest active state
    latest = mgr.get_latest_action_for_patient("A125")
    assert latest["clinician_selected_tier"] == "Tier A"
    assert latest["action"] == ACTION_ESCALATE


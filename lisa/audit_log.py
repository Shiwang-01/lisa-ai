"""LISA.ai — Clinician Actions & Audit Trail Engine (Milestone 7)

Provides append-only clinical audit event recording, safety-floor validated overrides,
and one-step operational escalation for human-in-the-loop decision support.

LISA remains decision support — NOT autonomous decision-making.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from lisa.sequencer import (
    TIER_A_CODE,
    TIER_B_CODE,
    TIER_C_CODE,
    TIER_D_CODE,
    TIER_E_CODE,
    TIER_ORDER
)

# Prototype Constants
DEFAULT_USER_ROLE = "TRIAGE_NURSE_01"
MODEL_VERSION = "LISA-RoW-v0.7"
RULE_VERSION = "LISA-Demo-Rules-v1"
SEQUENCER_VERSION = "LISA-SEQ-v1"

# Action Types
ACTION_ACCEPT = "ACCEPT"
ACTION_OVERRIDE = "OVERRIDE"
ACTION_ESCALATE = "ESCALATE"

# Standard Override Reasons
OVERRIDE_REASONS = [
    "CLINICAL_APPEARANCE",
    "NEW_INFORMATION",
    "PATIENT_DETERIORATION",
    "RESOURCE_CONSTRAINT",
    "CLINICIAN_JUDGMENT",
    "OTHER"
]

# Tier Escalation Mapping (one-step upward urgency)
ESCALATION_MAP = {
    TIER_E_CODE: TIER_D_CODE,
    TIER_D_CODE: TIER_C_CODE,
    TIER_C_CODE: TIER_B_CODE,
    TIER_B_CODE: TIER_A_CODE,
    TIER_A_CODE: TIER_A_CODE,
}


def calculate_escalated_tier(current_tier: str) -> str:
    """Calculates a one-step upward operational urgency tier.

    Args:
        current_tier: E.g. 'Tier E', 'Tier C', 'Tier A'.

    Returns:
        New escalated tier string (e.g. 'Tier D', 'Tier B', 'Tier A').
    """
    clean_tier = current_tier.split("—")[0].strip() if "—" in current_tier else current_tier.strip()
    return ESCALATION_MAP.get(clean_tier, clean_tier)


def validate_clinician_override(
    effective_safety_floor: Optional[int],
    target_tier: str,
    override_reason: Optional[str]
) -> Tuple[bool, Optional[str]]:
    """Validates whether a clinician override is legally permissible under safety floors.

    Args:
        effective_safety_floor: 1, 2, or None/other.
        target_tier: The chosen target tier (e.g. 'Tier A', 'Tier B', 'Tier C').
        override_reason: Reason code from OVERRIDE_REASONS.

    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str]).
    """
    clean_target = target_tier.split("—")[0].strip() if "—" in target_tier else target_tier.strip()

    if not override_reason or not str(override_reason).strip():
        return False, "Override requires an explicit clinical reason."

    target_rank = TIER_ORDER.get(clean_target)
    if target_rank is None:
        return False, f"Invalid target tier: {target_tier}"

    # Safety Floor Level 1: Cannot map below Tier A (Tier rank must be 1)
    if effective_safety_floor == 1 and target_rank > 1:
        return False, (
            "Override blocked: selected tier would violate the active operational safety floor. "
            "Patients with Effective Safety Floor Level 1 cannot be downgraded below Tier A."
        )

    # Safety Floor Level 2: Cannot map below Tier B (Tier rank must be <= 2)
    if effective_safety_floor == 2 and target_rank > 2:
        return False, (
            "Override blocked: selected tier would violate the active operational safety floor. "
            "Patients with Effective Safety Floor Level 2 cannot be downgraded below Tier B."
        )

    return True, None


def create_audit_event(
    patient_token: str,
    action: str,
    system_ranked_patient: Dict[str, Any],
    system_allocated_patient: Dict[str, Any],
    operational_mode: str = "NORMAL",
    user_role: str = DEFAULT_USER_ROLE,
    clinician_selected_tier: Optional[str] = None,
    current_active_tier: Optional[str] = None,
    override_reason: Optional[str] = None,
    override_note: Optional[str] = None,
    timestamp: Optional[str] = None,
    event_id: Optional[str] = None
) -> Dict[str, Any]:
    """Constructs a validated, standardized audit event.

    Args:
        patient_token: Simulated patient token (e.g. 'A125').
        action: ACTION_ACCEPT, ACTION_OVERRIDE, or ACTION_ESCALATE.
        system_ranked_patient: Ranked queue record from sequencer.
        system_allocated_patient: Allocation record from allocator.
        operational_mode: 'NORMAL' or 'SURGE_3X'.
        user_role: Role of the acting clinician.
        clinician_selected_tier: Target tier if action is OVERRIDE or ACCEPT.
        current_active_tier: Current active clinician tier (for multi-step escalation).
        override_reason: Reason if action is OVERRIDE.
        override_note: Optional free-text clinician note.
        timestamp: ISO format string (auto-generated if None).
        event_id: UUID string (auto-generated if None).

    Returns:
        Complete audit event dictionary.

    Raises:
        ValueError: If required fields are missing or safety floor is violated.
    """
    if not patient_token:
        raise ValueError("Audit event requires a valid patient token.")

    if action not in [ACTION_ACCEPT, ACTION_OVERRIDE, ACTION_ESCALATE]:
        raise ValueError(f"Invalid action: {action}")

    eff_floor = system_ranked_patient.get("effective_safety_floor")
    system_tier_code = system_ranked_patient.get("queue_tier_code", TIER_E_CODE)

    # Determine final clinician tier based on action
    if action == ACTION_ACCEPT:
        final_tier = clinician_selected_tier or system_tier_code
        reason_val = None
    elif action == ACTION_OVERRIDE:
        if not clinician_selected_tier:
            raise ValueError("Override requires a selected target tier.")
        is_valid, err = validate_clinician_override(eff_floor, clinician_selected_tier, override_reason)
        if not is_valid:
            raise ValueError(err)
        final_tier = clinician_selected_tier.split("—")[0].strip()
        reason_val = str(override_reason).strip()
    elif action == ACTION_ESCALATE:
        base_tier = current_active_tier or system_tier_code
        final_tier = calculate_escalated_tier(base_tier)
        reason_val = "CLINICAL_ESCALATION"
    else:
        final_tier = system_tier_code
        reason_val = None

    evt_time = timestamp or datetime.now().isoformat()
    evt_uuid = event_id or str(uuid.uuid4())

    return {
        "event_id": evt_uuid,
        "timestamp": evt_time,
        "user_role": user_role,
        "patient_token": patient_token,
        "operational_mode": operational_mode,
        "action": action,
        "system_queue_rank": system_ranked_patient.get("priority_rank"),
        "system_queue_tier": system_tier_code,
        "system_sequence_score": system_ranked_patient.get("sequence_score"),
        "initial_triage_level": system_ranked_patient.get("initial_triage_level"),
        "protocol_floor_level": system_ranked_patient.get("protocol_floor_level"),
        "effective_safety_floor": eff_floor,
        "current_risk": system_ranked_patient.get("current_risk"),
        "risk_60_min": system_ranked_patient.get("risk_60_min"),
        "confidence": system_ranked_patient.get("confidence"),
        "recheck_due_min": system_ranked_patient.get("recheck_due_min"),
        "system_resource_status": system_allocated_patient.get("allocation_status"),
        "system_bed_id": system_allocated_patient.get("bed_id"),
        "system_bed_type": system_allocated_patient.get("bed_type"),
        "clinician_selected_tier": final_tier,
        "override_reason": reason_val,
        "override_note": str(override_note).strip() if override_note else "",
        "model_version": MODEL_VERSION,
        "rule_version": RULE_VERSION,
        "sequencer_version": SEQUENCER_VERSION
    }


class AuditTrailManager:
    """Manages session-scoped append-only clinical audit events."""

    def __init__(self):
        self._events: List[Dict[str, Any]] = []

    def log_event(self, event: Dict[str, Any]) -> None:
        """Appends an event to the audit log."""
        self._events.append(event)

    def get_events(self) -> List[Dict[str, Any]]:
        """Returns all audit events in chronological order."""
        return list(self._events)

    def get_events_for_patient(self, patient_token: str) -> List[Dict[str, Any]]:
        """Returns audit events for a specific patient token."""
        return [e for e in self._events if e["patient_token"] == patient_token]

    def get_latest_action_for_patient(self, patient_token: str) -> Optional[Dict[str, Any]]:
        """Returns the most recent action record for a patient, if any."""
        patient_events = self.get_events_for_patient(patient_token)
        return patient_events[-1] if patient_events else None

    def clear(self) -> None:
        """Resets the session audit log."""
        self._events.clear()

    def count(self) -> int:
        """Returns the total number of logged events."""
        return len(self._events)

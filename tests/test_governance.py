import inspect
import re
import pytest

from lisa.governance import (
    get_governance_summary,
    EXCLUDED_PRIORITIZATION_FEATURES,
    ALLOCATOR_VERSION
)
from lisa.audit_log import (
    MODEL_VERSION,
    RULE_VERSION,
    SEQUENCER_VERSION
)
import lisa.protocol_floor as protocol_floor_mod
import lisa.risk_engine as risk_engine_mod
import lisa.sequencer as sequencer_mod
import lisa.allocator as allocator_mod
from lisa.surge_simulator import load_normal_cohort, load_surge_cohort


def test_governance_summary_sections():
    """Test 1: Governance summary returns all required structural sections."""
    gov = get_governance_summary()
    assert "clinical_safety_position" in gov
    assert "implemented_prototype_controls" in gov
    assert "unimplemented_production_requirements" in gov
    assert "implemented_vs_required_matrix" in gov
    assert "data_minimization_rules" in gov
    assert "excluded_prioritization_features" in gov
    assert "fairness_monitoring_dimensions" in gov
    assert "human_accountability_chain" in gov
    assert "regulatory_design_assumptions" in gov
    assert "model_and_rule_versions" in gov
    assert "data_flow_steps" in gov


def test_prototype_controls_and_synthetic_scope():
    """Tests 2, 3, 12: Prototype controls include tokenized synthetic IDs, simulated data only, and session audit scope."""
    gov = get_governance_summary()
    controls_str = " ".join(gov["implemented_prototype_controls"]).lower()

    assert "tokenized" in controls_str or "synthetic" in controls_str
    assert "simulated" in controls_str
    assert "audit" in controls_str


def test_unimplemented_production_requirements():
    """Tests 4 & 5: Governance explicitly discloses that authentication and production encryption are not implemented."""
    gov = get_governance_summary()
    unimplemented_str = " ".join(gov["unimplemented_production_requirements"]).lower()

    assert "authentication" in unimplemented_str or "idp" in unimplemented_str
    assert "encryption" in unimplemented_str or "aes" in unimplemented_str
    assert "role-based" in unimplemented_str or "rbac" in unimplemented_str or "access control" in unimplemented_str


def test_prohibited_prioritization_features_list():
    """Test 6: Prohibited prioritization features explicitly include financial, socioeconomic, and demographic biases."""
    gov = get_governance_summary()
    excluded = gov["excluded_prioritization_features"]

    assert "insurance_status" in excluded
    assert "payment_ability" in excluded
    assert "caste" in excluded
    assert "religion" in excluded
    assert "vip_status" in excluded
    assert "donation_history" in excluded
    assert "hospital_revenue_value" in excluded


def test_prioritization_modules_do_not_use_prohibited_features():
    """Test 7: Prioritization code modules (protocol_floor, risk_engine, sequencer, allocator) do not reference prohibited features."""
    modules = [protocol_floor_mod, risk_engine_mod, sequencer_mod, allocator_mod]

    prohibited_tokens = [
        "insurance",
        "payment",
        "caste",
        "religion",
        "socioeconomic",
        "vip_status",
        "donation",
        "revenue",
        "payer",
        "billing"
    ]

    for mod in modules:
        source = inspect.getsource(mod).lower()
        # Remove comments and docstrings before checking execution code
        cleaned_source = re.sub(r'""".*?"""', '', source, flags=re.DOTALL)
        cleaned_source = re.sub(r"'''.*?'''", '', cleaned_source, flags=re.DOTALL)
        cleaned_source = re.sub(r'#.*', '', cleaned_source)

        for token in prohibited_tokens:
            assert token not in cleaned_source, f"Prohibited feature '{token}' found in {mod.__name__} source code!"


def test_no_false_regulatory_compliance_claims():
    """Test 8: Governance explicitly avoids false claims of regulatory certification or formal clinical validation."""
    gov = get_governance_summary()
    gov_text = str(gov).lower()

    # Must NOT claim these certifications as achieved
    prohibited_claims = [
        "dpdp compliant",
        "hipaa compliant",
        "gdpr compliant",
        "abdm certified",
        "clinically validated",
        "fda approved"
    ]

    for claim in prohibited_claims:
        assert claim not in gov_text, f"Prohibited compliance claim '{claim}' found in governance metadata!"


def test_clinical_safety_position_and_human_accountability():
    """Tests 9, 10, 11: Governance states clinician accountability, and that LISA does not diagnose or prescribe."""
    gov = get_governance_summary()
    principles_str = " ".join(gov["clinical_safety_position"]["principles"]).lower()

    assert "does not diagnose" in principles_str
    assert "does not prescribe" in principles_str
    assert "clinician" in principles_str or "human" in principles_str

    chain_str = " ".join(gov["human_accountability_chain"]).lower()
    assert "clinician remains strictly accountable" in chain_str or "accountable" in chain_str


def test_fairness_monitoring_and_version_stamping():
    """Tests 13, 14, 15: Governance includes fairness monitoring dimensions and matching version constants."""
    gov = get_governance_summary()
    assert len(gov["fairness_monitoring_dimensions"]) >= 5

    versions = gov["model_and_rule_versions"]
    version_dict = {v["component"]: v["version"] for v in versions}

    assert version_dict["Clinical Protocol Guardrails"] == RULE_VERSION
    assert version_dict["Risk-of-Wait Engine"] == MODEL_VERSION
    assert version_dict["Dynamic Queue Sequencer"] == SEQUENCER_VERSION
    assert version_dict["Bed Capacity Allocator"] == ALLOCATOR_VERSION


def test_no_real_patient_identifiers_in_cohorts():
    """Test 16: Seed and surge cohorts only contain synthetic tokenized identifiers and no real contact or national ID columns."""
    df_normal = load_normal_cohort()
    df_surge = load_surge_cohort()

    forbidden_cols = ["name", "patient_name", "ssn", "aadhaar", "phone", "email", "address", "insurance_id"]

    for col in forbidden_cols:
        assert col not in df_normal.columns
        assert col not in df_surge.columns

    for token in df_normal["patient_token"]:
        assert re.match(r"^A\d{3}$", token)

    for token in df_surge["patient_token"]:
        assert re.match(r"^A\d{3}$", token)


def test_no_inaccurate_zero_external_dependencies_claim():
    """Fix 1: Project does not make inaccurate 'zero external dependencies' claims."""
    with open("README.md", "r", encoding="utf-8") as f:
        readme_text = f.read().lower()
    with open("docs/privacy_and_governance.md", "r", encoding="utf-8") as f:
        doc_text = f.read().lower()

    assert "zero external dependencies" not in readme_text
    assert "zero external dependencies" not in doc_text


def test_governance_does_not_overprescribe_mandatory_cryptography():
    """Fix 2: Governance does not present AES-256, TLS 1.3, FIPS 140-3, or HSM as universal mandatory requirements."""
    gov = get_governance_summary()
    matrix = gov["implemented_vs_required_matrix"]

    for row in matrix:
        req = row["production_requirement"].lower()
        # Verify requirement-category language is used instead of rigid universal tech mandates
        assert "fips" not in req
        assert "hsm" not in req
        assert "aes-256" not in req
        assert "tls 1.3" not in req


def test_fairness_dimensions_use_collected_sex_field():
    """Fix 3: Governance specifies sex-based monitoring and does not claim a gender field exists."""
    gov = get_governance_summary()
    dims = " ".join(gov["fairness_monitoring_dimensions"]).lower()

    assert "sex-based" in dims
    assert "using collected sex field" in dims


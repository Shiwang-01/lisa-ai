import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lisa.protocol_floor import evaluate_protocol_floor
from lisa.risk_engine import evaluate_risk_of_wait, RISK_BREACH_THRESHOLD
from lisa.sequencer import rank_waiting_queue
from lisa.allocator import load_beds_inventory, allocate_available_beds, STATUS_ALLOCATED
from lisa.surge_simulator import (
    get_operational_mode,
    compute_surge_summary,
    MODE_NORMAL,
    MODE_SURGE_3X
)
from lisa.comparison_metrics import compare_queue_policies
from lisa.audit_log import (
    AuditTrailManager,
    create_audit_event,
    validate_clinician_override,
    calculate_escalated_tier,
    ACTION_ACCEPT,
    ACTION_OVERRIDE,
    ACTION_ESCALATE,
    OVERRIDE_REASONS,
    DEFAULT_USER_ROLE
)
from lisa.governance import get_governance_summary

st.set_page_config(
    page_title="LISA.ai — ED Sequencing Prototype",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "audit_manager" not in st.session_state:
    st.session_state.audit_manager = AuditTrailManager()

# ---------------------------------------------------------
# Header & Disclaimer
# ---------------------------------------------------------
st.title("🏥 LISA.ai")
st.subheader("Dynamic ED Sequencing + Deterioration Safety Net")

st.warning(
    "⚠️ **Prototype simulation only — not for clinical use.**",
    icon="⚠️"
)

tab_ops, tab_gov = st.tabs(["📊 Operations & Queue Simulation", "🛡️ Privacy, Safety & Governance"])

with tab_ops:
    # ---------------------------------------------------------
    # Operational Mode Toggle (Milestone 6A)
    # ---------------------------------------------------------
    selected_mode_label = st.radio(
        "**Select Operational Mode:**",
        options=["Normal (20 Patients)", "Surge 3× (60 Patients)"],
        index=0,
        horizontal=True
    )

mode_code = MODE_SURGE_3X if "Surge" in selected_mode_label else MODE_NORMAL
mode_context = get_operational_mode(mode_code)
patients_df = mode_context["patients"]
beds_df = mode_context["beds_df"]

if mode_code == MODE_SURGE_3X:
    st.info(
        "🌊 **Surge 3× Simulation Active**  \n"
        "60 simulated waiting patients are competing for the same 8 ED spaces.  \n"
        "_Prototype operations simulation only — not for clinical use._"
    )

st.markdown("---")

# Evaluate Protocol Floors and Risk-of-Wait for entire cohort
floor_results = []
risk_results = []
display_floor_labels = []
current_risk_col = []
risk_60_col = []
confidence_col = []
reassess_col = []

for _, row in patients_df.iterrows():
    f_res = evaluate_protocol_floor(row)
    r_res = evaluate_risk_of_wait(row, f_res)

    floor_results.append(f_res)
    risk_results.append(r_res)

    if f_res["triggered"]:
        display_floor_labels.append(f"Level {f_res['floor_level']}")
    else:
        display_floor_labels.append("No Hard Floor")

    current_risk_col.append(r_res["current_risk"])
    risk_60_col.append(r_res["risk_60_min"])
    confidence_col.append(f"{r_res['confidence']}%")
    reassess_col.append(f"{r_res['recheck_due_min']} min")

patients_display_df = patients_df.copy()
patients_display_df.insert(1, "Protocol Floor", display_floor_labels)
patients_display_df.insert(2, "Current Risk", current_risk_col)
patients_display_df.insert(3, "60-min Risk", risk_60_col)
patients_display_df.insert(4, "Confidence", confidence_col)
patients_display_df.insert(5, "Reassess In", reassess_col)

# Evaluate Queue Sequencing for entire cohort (Milestone 4)
ranked_queue = rank_waiting_queue(patients_df)

# Evaluate Capacity-Aware Bed Allocation (Milestone 5)
allocation_results = allocate_available_beds(ranked_queue, beds_df)

# Compute Operational Pressure Summary (Milestone 6A)
surge_summary = compute_surge_summary(ranked_queue, allocation_results, len(beds_df), mode_code)

# ---------------------------------------------------------
# Operational Pressure Panel (Milestone 6A)
# ---------------------------------------------------------
st.markdown("### 📊 Operational Pressure Panel")
p_col1, p_col2, p_col3, p_col4 = st.columns(4)
p_col1.metric("👥 Waiting Patients", surge_summary["patient_count"])
p_col2.metric("🛏️ Available Beds", f"{surge_summary['available_bed_count']}")
p_col3.metric("📈 Patients / Bed", f"{surge_summary['patients_per_bed']}×")
p_col4.metric("👩‍⚕️ Patients / Triage Nurse", f"{surge_summary['patients_per_triage_nurse']}")

p2_col1, p2_col2, p2_col3, p2_col4 = st.columns(4)
p2_col1.metric("🚨 Reassess ≤ 5 min", f"{surge_summary['reassess_within_5_min']} patients")
p2_col2.metric("⏱️ Reassess ≤ 15 min", f"{surge_summary['reassess_within_15_min']} patients")
p2_col3.metric("⏳ Awaiting Suitable Bed", f"{surge_summary['waiting_suitable_bed_count']} patients")
p2_col4.metric("🛡️ Hard Protocol Floors", f"{surge_summary['hard_protocol_floor_count']} patients")

st.markdown("---")

# ---------------------------------------------------------
# Cohort Summary Metrics
# ---------------------------------------------------------
total_patients = len(patients_df)
pediatric_count = int((patients_df["age"] < 18).sum())
geriatric_count = int((patients_df["age"] >= 65).sum())
unavailable_records = int((patients_df["prior_record_available"].astype(str).str.strip().str.lower().isin(["no", "false", "0"])).sum())

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="👥 Patients Waiting", value=total_patients)
with col2:
    st.metric(label="👶 Pediatric Patients", value=pediatric_count)
with col3:
    st.metric(label="🧓 Geriatric Patients", value=geriatric_count)
with col4:
    st.metric(label="📁 Prior Records Unavailable", value=unavailable_records)

st.markdown("---")

# ---------------------------------------------------------
# Simulated Bed Capacity Summary (Milestone 5)
# ---------------------------------------------------------
total_beds = len(beds_df)
resus_beds = int((beds_df["bed_type"] == "Resus").sum())
monitored_beds = int((beds_df["bed_type"] == "Monitored").sum())
general_beds = int((beds_df["bed_type"] == "General").sum())
fast_track_beds = int((beds_df["bed_type"] == "Fast-track").sum())

b_col1, b_col2, b_col3, b_col4, b_col5 = st.columns(5)
b_col1.metric("🛏️ Available Beds", total_beds)
b_col2.metric("🚨 Resus", resus_beds)
b_col3.metric("📈 Monitored", monitored_beds)
b_col4.metric("🩺 General", general_beds)
b_col5.metric("⚡ Fast-track", fast_track_beds)

st.markdown("---")

queue_display_data = []
for p in ranked_queue:
    token = p["patient_token"]
    latest_action = st.session_state.audit_manager.get_latest_action_for_patient(token)
    if latest_action:
        act_type = latest_action["action"]
        if act_type == ACTION_ACCEPT:
            clin_action_str = "✅ Accepted"
        elif act_type == ACTION_OVERRIDE:
            clin_action_str = f"⚠️ Override → {latest_action['clinician_selected_tier']}"
        elif act_type == ACTION_ESCALATE:
            clin_action_str = f"⚡ Escalated → {latest_action['clinician_selected_tier']}"
        else:
            clin_action_str = "—"
    else:
        clin_action_str = "—"

    queue_display_data.append({
        "Rank": p["priority_rank"],
        "Patient": token,
        "Queue Tier": p["queue_tier"],
        "Clinician Action": clin_action_str,
        "Sequence Score": p["sequence_score"],
        "Current Risk": p["current_risk"],
        "60-min Risk": p["risk_60_min"],
        "Confidence": f"{p['confidence']}%",
        "Waiting": f"{p['arrival_minutes_ago']} min",
        "Reassess In": f"{p['recheck_due_min']} min",
        "Recommended Action": p["recommended_queue_action"]
    })
ranked_queue_df = pd.DataFrame(queue_display_data)

# ---------------------------------------------------------
# Recommended ED Queue (Milestone 4)
# ---------------------------------------------------------
st.markdown("### ⚡ Recommended ED Queue")
st.markdown(
    "**Operational sequencing** based on protocol guardrails, Risk-of-Wait trajectory, "
    "reassessment urgency, uncertainty, and time already waiting."
)
st.caption("⚠️ _Simulation recommendation only — clinician remains responsible for final prioritization._")

st.dataframe(
    ranked_queue_df,
    use_container_width=True,
    hide_index=True
)

st.markdown("---")

# ---------------------------------------------------------
# Recommended Resource Allocation (Milestone 5)
# ---------------------------------------------------------
st.markdown("### 🛏️ Recommended Resource Allocation")
st.markdown("**Capacity-aware simulation** using queue priority and resource compatibility.")
st.caption("⚠️ _Allocation recommendations are simulated operational support only. Final placement remains a clinician decision._")

alloc_display_df = pd.DataFrame(allocation_results["allocated_beds"])
alloc_display_df.columns = ["Bed", "Type", "Recommended Patient", "Rank", "Score", "Queue Tier", "Why"]
st.dataframe(
    alloc_display_df,
    use_container_width=True,
    hide_index=True
)

st.markdown("#### ⏳ Patients Awaiting Capacity")
st.caption("Simulation queue awaiting available compatible space or scheduled reassessment.")

waiting_display_data = []
for wp in allocation_results["waiting_patients"]:
    waiting_display_data.append({
        "Patient": wp["patient_token"],
        "Rank": f"#{wp['priority_rank']}",
        "Queue Tier": wp["queue_tier"],
        "Current Risk": wp["current_risk"],
        "Reassess In": f"{wp['recheck_due_min']} min",
        "Allocation Status": wp["allocation_status"]
    })
waiting_display_df = pd.DataFrame(waiting_display_data)
st.dataframe(
    waiting_display_df,
    use_container_width=True,
    hide_index=True
)

st.markdown("---")

# ---------------------------------------------------------
# Queue Policy Simulation (Milestone 6B)
# ---------------------------------------------------------
st.markdown("### 🔬 Queue Policy Simulation")
st.markdown(
    "**Static triage/FIFO baseline vs LISA dynamic sequencing** under identical simulated attention capacity."
)
st.caption("⚠️ **Simulation result — not clinical efficacy evidence.**")

policy_comparison = compare_queue_policies(patients_df)
static_metrics = policy_comparison["static_baseline"]
lisa_metrics = policy_comparison["lisa"]
diffs = policy_comparison["differences"]
assumptions = policy_comparison["simulation_assumptions"]

with st.expander("⚙️ Simulation Assumptions & Parameters", expanded=False):
    st.markdown(f"""
- **Simulation Horizon:** {assumptions['simulation_horizon_min']} minutes
- **Triage Nurse Count:** {assumptions['triage_nurses']}
- **Attention Slot Interval:** {assumptions['attention_slot_min']} minutes
- **Available Attention Slots:** {assumptions['available_attention_slots']} slots
- **Mechanical Capacity Ceilings (under this simplified slot model):**
  - Maximum patients that can receive attention by ≤ 5 min: **2**
  - Maximum patients that can receive attention by ≤ 15 min: **4**
  _(Attention slot times: 0 min, 5 min, 10 min, 15 min, ...)_
- **Queue Policies:**
  - **Static Baseline:** Initial triage level priority + FIFO within category (arrival waiting time)
  - **LISA Dynamic Sequencing:** Protocol guardrails + Risk-of-Wait trajectory + reassessment deadlines + uncertainty buffer + waiting time
""")

# Side-by-side metric comparison cards
m_col1, m_col2, m_col3 = st.columns(3)
with m_col1:
    st.metric(
        label="🚨 Reassessment Deadlines Missed",
        value=f"LISA: {lisa_metrics['reassessment_deadlines_missed']}",
        delta=f"Static: {static_metrics['reassessment_deadlines_missed']} (Diff: {diffs['reassessment_deadline_breaches_difference']})",
        delta_color="off"
    )
    st.metric(
        label="⏱️ Avg Reassessment Delay",
        value=f"LISA: {lisa_metrics['average_reassessment_delay_min']} min",
        delta=f"Static: {static_metrics['average_reassessment_delay_min']} min (Diff: {diffs['average_delay_difference_min']} min)",
        delta_color="off"
    )

with m_col2:
    st.metric(
        label="⚡ Urgent Patients Reviewed ≤ 15 min",
        value=f"LISA: {lisa_metrics['urgent_reviewed_within_15_min']} / {lisa_metrics['urgent_total']}",
        delta=f"Static: {static_metrics['urgent_reviewed_within_15_min']} / {static_metrics['urgent_total']} (Diff: {diffs['urgent_reviewed_15min_difference']:+d})",
        delta_color="off"
    )
    st.metric(
        label="📈 High Wait-Risk Reviewed ≤ 30 min",
        value=f"LISA: {lisa_metrics['high_wait_risk_reviewed_within_30_min']} / {lisa_metrics['high_wait_risk_total']}",
        delta=f"Static: {static_metrics['high_wait_risk_reviewed_within_30_min']} / {static_metrics['high_wait_risk_total']} (Diff: {diffs['high_wait_risk_reviewed_30min_difference']:+d})",
        delta_color="off"
    )

with m_col3:
    st.metric(
        label="🔄 Dynamic-Priority Inversions",
        value=f"LISA: {lisa_metrics['lower_urgency_ahead_of_urgent_count']}",
        delta=f"Static: {static_metrics['lower_urgency_ahead_of_urgent_count']} (Diff: {diffs['priority_inversion_difference']})",
        delta_color="off"
    )
    st.metric(
        label="🛡️ Protocol Floors Reviewed ≤ 5 min",
        value=f"LISA: {lisa_metrics['protocol_floor_reviewed_within_5_min']} / {lisa_metrics['protocol_floor_total']}",
        delta=f"Static: {static_metrics['protocol_floor_reviewed_within_5_min']} / {static_metrics['protocol_floor_total']} (Diff: {diffs['protocol_floor_reviewed_5min_difference']:+d})",
        delta_color="off"
    )

st.caption(
    f"📊 **Attention Coverage:** Both policies reviewed {lisa_metrics['reviewed_within_horizon']} / {assumptions['patient_count']} patients "
    f"within {assumptions['simulation_horizon_min']} min using the same {assumptions['available_attention_slots']} available slots."
)

with st.expander("🔍 Patient-Level Simulation Details", expanded=False):
    patient_sim_data = []
    for p in policy_comparison["patient_level_results"]:
        patient_sim_data.append({
            "Patient": p["patient_token"],
            "Static Rank": f"#{p['static_rank']}",
            "LISA Rank": f"#{p['lisa_rank']}",
            "Static Attention": f"{p['static_attention_min']} min" if p["static_attention_min"] is not None else "Not reviewed",
            "LISA Attention": f"{p['lisa_attention_min']} min" if p["lisa_attention_min"] is not None else "Not reviewed",
            "Reassess Due": f"{p['recheck_due_min']} min",
            "Static Deadline Miss": "⚠️ Missed" if p["static_deadline_missed"] else "✅ Met",
            "LISA Deadline Miss": "⚠️ Missed" if p["lisa_deadline_missed"] else "✅ Met",
            "Queue Tier": p["queue_tier"],
            "60-min Risk": p["60_min_risk"]
        })
    st.dataframe(
        pd.DataFrame(patient_sim_data),
        use_container_width=True,
        hide_index=True
    )

st.markdown("---")

# ---------------------------------------------------------
# Patient Cohort Data Table (Original Ordering Maintained)
# ---------------------------------------------------------
st.markdown("### 📋 Waiting ED Cohort")
st.dataframe(
    patients_display_df,
    use_container_width=True,
    hide_index=True
)

st.markdown("---")

# ---------------------------------------------------------
# Patient Inspection View
# ---------------------------------------------------------
st.markdown("### 🔍 Patient Inspection")

patient_tokens = patients_df["patient_token"].tolist()
options = [f"{token} — {patients_df.loc[patients_df['patient_token'] == token, 'complaint_text'].values[0]}" for token in patient_tokens]

selected_option = st.selectbox(
    "Select patient",
    options=options,
    index=0
)

selected_token = selected_option.split(" — ")[0]
selected_idx = patient_tokens.index(selected_token)
patient = patients_df.iloc[selected_idx]
patient_floor = floor_results[selected_idx]
patient_risk = risk_results[selected_idx]

# Display patient details in structured cards/columns
st.markdown(f"#### Patient Record: **{patient['patient_token']}**")

info_col1, info_col2, info_col3 = st.columns([1, 1, 1])

with info_col1:
    st.markdown("**Demographics & Status**")
    st.write(f"- **Age / Sex:** {patient['age']} yrs / {patient['sex']}")
    st.write(f"- **Language:** {patient['language']}")
    st.write(f"- **Pregnancy Status:** {patient['pregnancy_status']}")
    st.write(f"- **Arrived:** {patient['arrival_minutes_ago']} mins ago")

with info_col2:
    st.markdown("**Triage & Clinical Presentation**")
    st.write(f"- **Initial Triage Level:** ESI {patient['initial_triage_level']}")
    st.write(f"- **Mental Status:** {patient['mental_status']}")
    st.write(f"- **Visible Distress:** {patient['visible_distress']}")
    st.write(f"- **Pain Score:** {patient['pain_score']} / 10")

with info_col3:
    st.markdown("**Records & Resources**")
    st.write(f"- **Prior Records Available:** {patient['prior_record_available']}")
    st.write(f"- **Estimated Resource Need:** {patient['resource_need']}")
    st.write(f"- **Case Notes:** {patient['case_notes']}")

st.markdown("##### 🩺 Chief Complaint")
st.info(f"**{patient['complaint_text']}**")

st.markdown("##### 📊 Vital Signs")
vital_cols = st.columns(5)
vital_cols[0].metric(label="Heart Rate", value=f"{patient['heart_rate']} bpm")
vital_cols[1].metric(label="Respiratory Rate", value=f"{patient['respiratory_rate']} /min")
vital_cols[2].metric(label="Blood Pressure", value=f"{patient['systolic_bp']}/{patient['diastolic_bp']} mmHg")
vital_cols[3].metric(label="SpO2", value=f"{patient['spo2']}%")
vital_cols[4].metric(label="Temperature", value=f"{patient['temperature']} °C")

st.markdown("##### 📜 Known Medical History")
st.write(patient["known_history"])

# ---------------------------------------------------------
# Clinical Guardrails Section (Milestone 2)
# ---------------------------------------------------------
st.markdown("---")
st.markdown("### 🛡️ Clinical Guardrails")

urgency_names = {
    1: "Immediate / Critical",
    2: "Emergent",
    3: "Urgent",
    4: "Less Urgent",
    5: "Non-Urgent"
}

if patient_floor["triggered"]:
    floor_lvl = patient_floor["floor_level"]
    urgency_label = urgency_names.get(floor_lvl, "Emergent")
    st.error(f"**Protocol Floor:** Level {floor_lvl} — {urgency_label}")

    st.markdown("**Triggered Rules:**")
    for r_id, reason in zip(patient_floor["rule_ids"], patient_floor["reasons"]):
        st.markdown(f"• **{r_id}** — {reason}")

    st.markdown("**Status:**")
    st.markdown(
        f"🔒 **Hard safety floor active.** Future LISA scoring may escalate this patient "
        f"but cannot downgrade them below **Level {floor_lvl}**."
    )
else:
    st.success("**Protocol Floor:** No Hard Floor")
    st.markdown(
        "No hard protocol rule triggered from currently available simulated information.\n\n"
        "_This does NOT mean the patient is safe or low risk. Further risk-of-wait assessment "
        "will be performed by later modules._"
    )
# Risk of Waiting Section (Milestone 3)
# ---------------------------------------------------------
st.markdown("---")
st.markdown("### ⏱️ Risk of Waiting")

has_hard_floor = patient_floor["triggered"] and patient_floor["floor_level"] in [1, 2]

# Protocol Floor Priority Banner over Breach Clock
if has_hard_floor:
    st.error(
        f"🚨 **Protocol Floor Active (Level {patient_floor['floor_level']})** — "
        f"Hard safety guardrail takes precedence over waiting projections. "
        f"**Reassessment Due: {patient_risk['recheck_due_min']} min**",
        icon="🚨"
    )

# Risk trajectory scores
row_col1, row_col2, row_col3, row_col4 = st.columns(4)
row_col1.metric("Current Risk", f"{patient_risk['current_risk']} / 100")
row_col2.metric("30 min Wait", f"{patient_risk['risk_30_min']} / 100")
row_col3.metric("60 min Wait", f"{patient_risk['risk_60_min']} / 100")
row_col4.metric("120 min Wait", f"{patient_risk['risk_120_min']} / 100")

meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)

meta_col1.metric("Risk Band", patient_risk["risk_band"])
meta_col2.metric("Confidence", f"{patient_risk['confidence']}%")

# Risk Breach Clock display logic: Protocol floor takes visual precedence
if has_hard_floor and patient_risk["time_to_breach_min"] != 0:
    meta_col3.metric("Risk Breach Clock", "Secondary Metric")
    meta_col3.caption("Protocol floor already requires urgent reassessment")
elif patient_risk["time_to_breach_min"] == 0:
    meta_col3.metric("Risk Breach Clock", "⚠️ Breached (0 min)")
    meta_col3.caption("Already at/above breach threshold")
elif patient_risk["time_to_breach_min"] is not None:
    meta_col3.metric("Risk Breach Clock", f"~{patient_risk['time_to_breach_min']} min")
    meta_col3.caption("Estimated threshold breach")
else:
    meta_col3.metric("Risk Breach Clock", ">120 min")
    meta_col3.caption("No breach in 2h horizon")

meta_col4.metric("Reassessment Due", f"{patient_risk['recheck_due_min']} min")

st.caption("⚠️ **Safety Notice:** Risk Breach Clock is a simulation threshold heuristic, NOT a safe-wait recommendation. Always adhere to Reassessment Due deadlines.")

# Plotly Risk-of-Wait Line Chart
fig = go.Figure()

time_points = ["Now", "30 min", "60 min", "120 min"]
risk_points = [
    patient_risk["current_risk"],
    patient_risk["risk_30_min"],
    patient_risk["risk_60_min"],
    patient_risk["risk_120_min"]
]

fig.add_trace(go.Scatter(
    x=time_points,
    y=risk_points,
    mode="lines+markers+text",
    text=[str(r) for r in risk_points],
    textposition="top center",
    line=dict(color="#d9534f" if patient_risk["current_risk"] >= 50 else "#f0ad4e", width=3),
    marker=dict(size=9),
    name="Projected Risk of Wait"
))

# Breach threshold reference line
fig.add_hline(
    y=RISK_BREACH_THRESHOLD,
    line_dash="dash",
    line_color="#c9302c",
    annotation_text=f"Breach Threshold ({RISK_BREACH_THRESHOLD})",
    annotation_position="bottom right"
)

fig.update_layout(
    title="Simulated Risk-of-Wait Trajectory",
    xaxis_title="Simulated Waiting Horizon",
    yaxis_title="Risk-of-Wait Score (0–100)",
    yaxis=dict(range=[0, 105]),
    height=340,
    margin=dict(l=40, r=40, t=50, b=40),
)

st.plotly_chart(fig, use_container_width=True)
st.caption("ℹ️ _Simulation heuristic — not a clinical prediction._")

# Human-Readable Explanations: Why this score?
st.markdown("#### 💡 Why this score?")

why_col1, why_col2 = st.columns(2)

with why_col1:
    st.markdown("**Contributing Risk Factors:**")
    if patient_risk["risk_factors"]:
        for factor in patient_risk["risk_factors"]:
            st.markdown(f"- {factor}")
    else:
        st.write("No major physiological or clinical risk red flags detected.")

with why_col2:
    st.markdown("**Uncertainty & Data Reliability Factors:**")
    if patient_risk["uncertainty_factors"]:
        for u_factor in patient_risk["uncertainty_factors"]:
            st.markdown(f"- ⚠️ {u_factor}")
    else:
        st.write("Complete vital signs and prior medical records available.")

# Technical & Debug Details (Expandable)
with st.expander("🛠️ Technical simulation details & explanation codes"):
    if has_hard_floor and patient_risk["time_to_breach_min"] is not None and patient_risk["time_to_breach_min"] > 0:
        st.info(
            f"ℹ️ **Model threshold estimate:** ~{patient_risk['time_to_breach_min']} min  \n"
            f"_Secondary metric only — protocol floor active (Level {patient_floor['floor_level']}) "
            f"already requires urgent reassessment within {patient_risk['recheck_due_min']} min._"
        )
    st.write(f"- **Deterioration Slope:** {patient_risk['deterioration_slope']} pts / 30 min")
    st.write(f"- **Machine Explanation Codes:** `{', '.join(patient_risk['explanation_codes'])}`")
    st.write(f"- **Breach Threshold Set Point:** {RISK_BREACH_THRESHOLD}")

# ---------------------------------------------------------
# Queue Recommendation Section (Milestone 4)
# ---------------------------------------------------------
st.markdown("---")
st.markdown("### 🎯 Queue Recommendation")

# Lookup selected patient in ranked_queue
patient_ranked = next(p for p in ranked_queue if p["patient_token"] == selected_token)

q_col1, q_col2, q_col3, q_col4 = st.columns(4)
q_col1.metric("Priority Rank", f"#{patient_ranked['priority_rank']} / {total_patients}")
q_col2.metric("Operational Queue Tier", patient_ranked["queue_tier"])
q_col3.metric("Sequence Score", f"{patient_ranked['sequence_score']} / 100")
q_col4.metric("Recommended Action", patient_ranked["recommended_queue_action"])

# Operational Safety Floor Breakdown
init_lvl = patient_ranked.get("initial_triage_level")
proto_lvl = patient_ranked.get("protocol_floor_level")
eff_floor = patient_ranked.get("effective_safety_floor")
eff_src = patient_ranked.get("effective_safety_floor_source")

sf_col1, sf_col2, sf_col3 = st.columns(3)
sf_col1.metric("Initial Clinician Triage", f"Level {init_lvl}" if init_lvl else "Not recorded")
sf_col2.metric("Protocol Guardrail", f"Level {proto_lvl}" if proto_lvl else "No hard floor")
if eff_floor:
    if eff_src == "CLINICIAN_TRIAGE":
        eff_label = f"Level {eff_floor} (Clinician triage takes precedence)"
    elif eff_src == "PROTOCOL_GUARDRAIL":
        eff_label = f"Level {eff_floor} (Protocol guardrail safety floor)"
    elif eff_src == "BOTH":
        eff_label = f"Level {eff_floor} (Clinician & protocol concordant)"
    else:
        eff_label = f"Level {eff_floor}"
else:
    eff_label = "No safety floor active"
sf_col3.metric("Effective Operational Safety Floor", eff_label)

st.markdown("#### 🔍 Why this patient is prioritized here:")
for reason in patient_ranked["sequence_reasons"]:
    st.markdown(f"- {reason}")

with st.expander("🛠️ Technical Sequencing Details & Machine Codes"):
    st.write(f"- **Tier Category:** `{patient_ranked['queue_tier_code']}` ({patient_ranked['queue_tier_name']})")
    st.write(f"- **Effective Safety Floor:** `Level {eff_floor}` (Source: `{eff_src}`)")
    st.write(f"- **Machine Sequencing Codes:** `{', '.join(patient_ranked['sequence_codes'])}`")
    st.write(f"- **Arrival Elapsed Time:** {patient_ranked['arrival_minutes_ago']} min")
    st.write(f"- **Sequence Score Formula:** `30% Current Risk + 30% 60m Risk + 15% Breach Urgency + 10% Reassess Urgency + 10% Uncertainty + 5% Wait Time`")

# ---------------------------------------------------------
# Resource Recommendation Section (Milestone 5)
# ---------------------------------------------------------
st.markdown("---")
st.markdown("### 🛏️ Resource Recommendation")

# Lookup selected patient in allocation_results
patient_alloc = next(p for p in allocation_results["patient_allocations"] if p["patient_token"] == selected_token)

r_col1, r_col2, r_col3 = st.columns(3)

if patient_alloc["allocation_status"] == STATUS_ALLOCATED:
    r_col1.metric("Allocation Status", "✅ Allocated")
    r_col2.metric("Recommended Bed", f"{patient_alloc['bed_id']} — {patient_alloc['bed_type']}")
    r_col3.metric("Minimum Resource Need", patient_alloc["minimum_resource_level"])

    st.success(f"**Operational Placement:** {patient_alloc['allocation_reason']}")
    st.markdown("#### 🔍 Clinical Compatibility Rationale:")
    for reason in patient_alloc["allocation_reasons"]:
        st.markdown(f"- {reason}")
else:
    r_col1.metric("Allocation Status", f"⏳ {patient_alloc['allocation_status']}")
    r_col2.metric("Recommended Bed Types", " / ".join(patient_alloc["preferred_bed_types"]))
    r_col3.metric("Reassessment Deadline", f"{patient_alloc['recheck_due_min']} min")

    st.warning(f"**Operational Status:** {patient_alloc['allocation_reason']}")
    st.markdown("#### 🔍 Clinical Compatibility Profile:")
    for reason in patient_alloc["allocation_reasons"]:
        st.markdown(f"- {reason}")
    st.caption("⚠️ _Unallocated status does NOT imply waiting is safe. Mandatory clinical reassessment deadline remains active._")

with st.expander("🛠️ Technical Resource Compatibility Details"):
    st.write(f"- **Preferred Bed Types:** `{', '.join(patient_alloc['preferred_bed_types'])}`")
    st.write(f"- **Acceptable Bed Types:** `{', '.join(patient_alloc['acceptable_bed_types'])}`")
    st.write(f"- **Incompatible Bed Types:** `{', '.join(patient_alloc['incompatible_bed_types'])}`")
    st.write(f"- **Resource Compatibility Codes:** `{', '.join(patient_alloc['allocation_codes'])}`")

# ---------------------------------------------------------
# Clinician Actions Section (Milestone 7)
# ---------------------------------------------------------
st.markdown("---")
st.markdown("### 🎯 Clinician Action")
st.caption(f"👤 Acting as: `{DEFAULT_USER_ROLE}` | _Human-in-the-loop decision support._")

latest_p_action = st.session_state.audit_manager.get_latest_action_for_patient(selected_token)

ca_col1, ca_col2 = st.columns(2)
with ca_col1:
    st.markdown(f"**System Queue Recommendation:** `{patient_ranked['queue_tier']}`")
with ca_col2:
    if latest_p_action:
        act_type = latest_p_action["action"]
        if act_type == ACTION_ACCEPT:
            st.info(f"**Current Clinician State:** ✅ Recommendation Accepted (`{latest_p_action['clinician_selected_tier']}`)")
        elif act_type == ACTION_OVERRIDE:
            st.warning(f"**Current Clinician State:** ⚠️ Override Active (`{latest_p_action['clinician_selected_tier']}`) — Reason: `{latest_p_action['override_reason']}`")
        elif act_type == ACTION_ESCALATE:
            st.warning(f"**Current Clinician State:** ⚡ Escalation Active (`{latest_p_action['clinician_selected_tier']}`)")
    else:
        st.write("**Current Clinician State:** _No override (system recommendation active)_")

action_btn_col1, action_btn_col2, action_btn_col3 = st.columns([1, 1, 2])

with action_btn_col1:
    if st.button("✅ Accept Recommendation", key=f"accept_{selected_token}", use_container_width=True):
        evt = create_audit_event(
            patient_token=selected_token,
            action=ACTION_ACCEPT,
            system_ranked_patient=patient_ranked,
            system_allocated_patient=patient_alloc,
            operational_mode=mode_code,
            user_role=DEFAULT_USER_ROLE
        )
        st.session_state.audit_manager.log_event(evt)
        st.success("Recommendation accepted and recorded in audit log.")
        st.rerun()

with action_btn_col2:
    if st.button("⚡ Escalate Urgency", key=f"escalate_{selected_token}", use_container_width=True):
        current_clin_tier = latest_p_action["clinician_selected_tier"] if latest_p_action else None
        evt = create_audit_event(
            patient_token=selected_token,
            action=ACTION_ESCALATE,
            system_ranked_patient=patient_ranked,
            system_allocated_patient=patient_alloc,
            operational_mode=mode_code,
            user_role=DEFAULT_USER_ROLE,
            current_active_tier=current_clin_tier
        )
        st.session_state.audit_manager.log_event(evt)
        st.success(f"Urgency escalated to {evt['clinician_selected_tier']} and recorded in audit log.")
        st.rerun()

# Override Expander / Form
with st.expander("⚠️ Clinician Override Form", expanded=False):
    st.markdown("**Override Operational Queue Tier**")
    st.caption("Requires explicit clinical reasoning. Overrides cannot violate active safety floors.")

    ov_tier = st.selectbox(
        "Target Operational Tier:",
        options=["Tier A", "Tier B", "Tier C", "Tier D", "Tier E"],
        index=["Tier A", "Tier B", "Tier C", "Tier D", "Tier E"].index(patient_ranked["queue_tier_code"]) if patient_ranked["queue_tier_code"] in ["Tier A", "Tier B", "Tier C", "Tier D", "Tier E"] else 0,
        key=f"ov_tier_{selected_token}"
    )

    ov_reason = st.selectbox(
        "Override Reason (Required):",
        options=[""] + OVERRIDE_REASONS,
        format_func=lambda x: "Select a reason..." if x == "" else x,
        key=f"ov_reason_{selected_token}"
    )

    ov_note = st.text_area(
        "Clinician Note (Optional):",
        placeholder="Document clinical observations or rationale...",
        key=f"ov_note_{selected_token}"
    )

    if st.button("💾 Save Override", key=f"save_ov_{selected_token}"):
        if not ov_reason:
            st.error("Override requires an explicit clinical reason.")
        else:
            eff_floor = patient_ranked.get("effective_safety_floor")
            is_valid, err_msg = validate_clinician_override(eff_floor, ov_tier, ov_reason)
            if not is_valid:
                st.error(f"❌ {err_msg}")
                st.markdown(f"""
- **Initial Clinician Triage:** Level {patient_ranked.get('initial_triage_level') or 'None'}
- **Protocol Guardrail:** Level {patient_ranked.get('protocol_floor_level') or 'None'}
- **Effective Safety Floor:** Level {eff_floor or 'None'}
""")
            else:
                evt = create_audit_event(
                    patient_token=selected_token,
                    action=ACTION_OVERRIDE,
                    system_ranked_patient=patient_ranked,
                    system_allocated_patient=patient_alloc,
                    operational_mode=mode_code,
                    user_role=DEFAULT_USER_ROLE,
                    clinician_selected_tier=ov_tier,
                    override_reason=ov_reason,
                    override_note=ov_note
                )
                st.session_state.audit_manager.log_event(evt)
                st.success(f"Override to {ov_tier} saved and recorded in audit log.")
                st.rerun()

# ---------------------------------------------------------
# Clinical Audit Trail Section (Milestone 7)
# ---------------------------------------------------------
st.markdown("---")
st.markdown("### 📜 Clinical Audit Trail")
st.caption("Demo audit log — session-scoped append-only event record.")

col_audit_info, col_audit_reset = st.columns([3, 1])
with col_audit_info:
    event_count = st.session_state.audit_manager.count()
    st.write(f"Total Logged Actions in Session: **{event_count}**")
with col_audit_reset:
    if st.button("🔄 Reset Demo Actions", key="reset_demo_actions", use_container_width=True):
        st.session_state.audit_manager.clear()
        st.success("Session audit trail and clinician actions reset.")
        st.rerun()

events = st.session_state.audit_manager.get_events()
if events:
    audit_rows = []
    for e in reversed(events):  # Newest first in display
        audit_rows.append({
            "Timestamp": e["timestamp"],
            "Event ID": e["event_id"][:8] + "...",
            "User": e["user_role"],
            "Patient": e["patient_token"],
            "Mode": e["operational_mode"],
            "Action": e["action"],
            "System Tier": e["system_queue_tier"],
            "Clinician Tier": e["clinician_selected_tier"],
            "Sequence Score": e["system_sequence_score"],
            "Override Reason": e["override_reason"] or "—",
            "Model Version": e["model_version"],
            "Rule Version": e["rule_version"]
        })
    st.dataframe(
        pd.DataFrame(audit_rows),
        use_container_width=True,
        hide_index=True
    )

    with st.expander("🔍 Inspect Full Audit Event Payloads", expanded=False):
        for i, e in enumerate(reversed(events), start=1):
            st.markdown(f"**Event #{event_count - i + 1} — {e['patient_token']} ({e['action']}) at {e['timestamp']}**")
            st.json(e)
else:
    st.info("No clinician actions logged in this session yet. Use the Patient Inspector to accept, escalate, or override recommendations.")

# ---------------------------------------------------------
# Tab 2: Privacy, Safety & Governance Specification (Milestone 8)
# ---------------------------------------------------------
with tab_gov:
    st.markdown("## 🛡️ Privacy, Safety & Governance Specification")
    st.info(
        "📋 **Governance Framework:** This panel documents the safety architecture, implemented prototype safeguards, "
        "production requirements, data minimization standards, and anti-bias invariants governing LISA.ai.  \n"
        "_Prototype simulation only — not for clinical use._"
    )

    gov = get_governance_summary()

    # 1. Clinical Safety Positioning
    st.markdown("### 1. 🏥 Clinical Safety Positioning")
    st.markdown(f"**{gov['clinical_safety_position']['statement']}**")
    for principle in gov["clinical_safety_position"]["principles"]:
        st.markdown(f"- {principle}")

    st.markdown("---")

    # 2. Implemented Safeguards vs Production Requirements
    st.markdown("### 2. ⚖️ Implemented Safeguards vs Production Requirements")
    st.caption("Transparent disclosure of prototype engineering controls versus full hospital production requirements.")

    matrix_df = pd.DataFrame(gov["implemented_vs_required_matrix"])
    matrix_df.columns = ["Domain", "Prototype Implementation", "Prototype Status", "Production Requirement", "Production Status"]
    st.dataframe(matrix_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # 3. Data Minimization & Synthetic Data Scope
    st.markdown("### 3. 🔒 Data Minimization & Synthetic Scope")
    for rule in gov["data_minimization_rules"]:
        st.markdown(f"- {rule}")

    st.markdown("---")

    # 4. Excluded Prioritization Features (Anti-Bias Invariant)
    st.markdown("### 4. 🚫 Excluded Prioritization Features (Anti-Bias Invariant)")
    st.markdown(
        "To prevent socioeconomic, financial, and institutional bias, the following attributes are **strictly excluded** "
        "from clinical protocol rules, Risk-of-Wait scoring, queue sequencing, and bed allocation:"
    )

    ex_col1, ex_col2 = st.columns(2)
    with ex_col1:
        st.markdown("**Financial & Socioeconomic Demographics:**")
        st.markdown("- Insurance status / Payer category")
        st.markdown("- Payment ability / Deposit status")
        st.markdown("- Socioeconomic class")
        st.markdown("- Caste & Religion")
    with ex_col2:
        st.markdown("**Institutional & Commercial Influences:**")
        st.markdown("- VIP status / Executive relationships")
        st.markdown("- Donation history")
        st.markdown("- Hospital revenue / Billing tier")
        st.markdown("- Room category preference")

    st.markdown("---")

    # 5. Human Accountability Chain
    st.markdown("### 5. 👤 Human-in-the-Loop Accountability")
    st.markdown(
        "LISA does not make autonomous decisions. The human clinician retains full authority and accountability at every stage:"
    )
    for step in gov["human_accountability_chain"]:
        st.markdown(f"- {step}")

    st.markdown("---")

    # 6. Auditability & Version Governance
    st.markdown("### 6. 📜 Auditability & Engine Versions")
    st.markdown(
        "Every clinical action is captured in an append-only audit trail with active model and rule version stamping. "
        "_Prototype audit log is session-scoped; production deployment requires durable, tamper-evident WORM storage._"
    )

    versions_df = pd.DataFrame(gov["model_and_rule_versions"])
    versions_df.columns = ["Component", "Engine Type", "Version Tag", "Scope & Responsibility"]
    st.dataframe(versions_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # 7. Subgroup Fairness Monitoring Plan
    st.markdown("### 7. 🔍 Subgroup Fairness Monitoring Plan")
    st.markdown(
        "LISA does not claim to be 'unbiased'. Production validation requires continuous performance disparity monitoring across:"
    )
    for dim in gov["fairness_monitoring_dimensions"]:
        st.markdown(f"- {dim}")

    st.markdown("---")

    # 8. Regulatory Design Assumptions
    st.markdown("### 8. 🌐 Regulatory Design Assumptions")
    reg = gov["regulatory_design_assumptions"]

    r_col1, r_col2 = st.columns(2)
    with r_col1:
        st.markdown("#### 🇮🇳 India Deployment Focus")
        st.markdown(f"**Framework Reference:** {reg['india_focus']['frameworks']}")
        st.caption(f"⚠️ {reg['india_focus']['disclaimer']}")
    with r_col2:
        st.markdown("#### 🌍 International Expansion")
        st.markdown(f"**Framework Reference:** {reg['international_expansion']['frameworks']}")
        st.caption(f"⚠️ {reg['international_expansion']['disclaimer']}")

    st.markdown("---")

    # 9. End-to-End Data Flow
    st.markdown("### 9. 🔄 End-to-End Decision Flow")
    st.code(" → ".join(gov["data_flow_steps"]), language="text")
    st.caption("🔒 _Synthetic environment only — no real patient data is ingested, processed, or transmitted._")

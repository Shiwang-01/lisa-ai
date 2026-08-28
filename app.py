import textwrap
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

# Load custom CSS
css_file_path = os.path.join(os.path.dirname(__file__), "lisa", "lisa_styles.css")
if os.path.exists(css_file_path):
    with open(css_file_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Custom Header Topbar
st.markdown(
    textwrap.dedent(f"""
    <div class="topbar-custom">
        <div class="brand-custom">
            <div class="brand-logo-custom">L</div>
            <div class="brand-text-custom">
                <div class="name">LISA<span>.ai</span></div>
                <div class="tagline">Right Patient. Right Bed. Right Time.</div>
            </div>
        </div>
        <div class="user-chip-custom">
            <div class="user-avatar-custom">TN</div>
            <div>Demo User: <b>{DEFAULT_USER_ROLE}</b></div>
        </div>
    </div>
    """),
    unsafe_allow_html=True
)

st.markdown('<div class="disclaimer-strip">⚠️ <b>Prototype simulation only — not for clinical use.</b></div>', unsafe_allow_html=True)

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
        st.markdown(
            textwrap.dedent("""
            <div style="background-color: #FCF3E0; border: 1px solid #B7791F; border-left: 4px solid #B7791F; border-radius: 8px; padding: 12px 16px; margin: 12px 0; color: #4A3500;">
                <div style="font-weight: 600; font-size: 15px; margin-bottom: 4px;">🌊 Surge 3× Simulation Active</div>
                <div style="font-size: 14px; margin-bottom: 2px;">60 simulated waiting patients are competing for the same 8 ED spaces.</div>
                <div style="font-size: 12px; font-style: italic; color: #7A5800;">Prototype operations simulation only — not for clinical use.</div>
            </div>
            """),
            unsafe_allow_html=True
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
    st.markdown(
        f"""
        <div class="kpi-container-custom">
            <div class="kpi-card-custom">
                <div class="label-custom">Waiting Patients</div>
                <div class="value-custom">{surge_summary['patient_count']}</div>
                <div class="desc-custom">Local ED cohort</div>
            </div>
            <div class="kpi-card-custom">
                <div class="label-custom">Available Beds</div>
                <div class="value-custom">{surge_summary['available_bed_count']}</div>
                <div class="desc-custom">{resus_beds} Resus · {monitored_beds} Mon · {general_beds} Gen · {fast_track_beds} FT</div>
            </div>
            <div class="kpi-card-custom">
                <div class="label-custom">Patients / Bed</div>
                <div class="value-custom">{surge_summary['patients_per_bed']}×</div>
                <div class="desc-custom">Triage ratio</div>
            </div>
            <div class="kpi-card-custom">
                <div class="label-custom">Triage Nurse</div>
                <div class="value-custom">1</div>
                <div class="desc-custom">Single-nurse simulation</div>
            </div>
            <div class="kpi-card-custom urgent">
                <div class="label-custom">Reassess ≤ 5 min</div>
                <div class="value-custom">{surge_summary['reassess_within_5_min']}</div>
                <div class="desc-custom">High urgency window</div>
            </div>
            <div class="kpi-card-custom warn">
                <div class="label-custom">Reassess ≤ 15 min</div>
                <div class="value-custom">{surge_summary['reassess_within_15_min']}</div>
                <div class="desc-custom">Cumulative window</div>
            </div>
            <div class="kpi-card-custom">
                <div class="label-custom">Awaiting Bed</div>
                <div class="value-custom">{surge_summary['waiting_suitable_bed_count']}</div>
                <div class="desc-custom">Capacity-constrained</div>
            </div>
            <div class="kpi-card-custom accent">
                <div class="label-custom">Hard Floors</div>
                <div class="value-custom">{surge_summary['hard_protocol_floor_count']}</div>
                <div class="desc-custom">Guardrail-locked minimums</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

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

    # Render Recommended ED Queue as Custom HTML Table
    queue_rows = []
    for row in queue_display_data:
        tier_letter = row["Queue Tier"].split()[1] if len(row["Queue Tier"].split()) > 1 else "E"
        queue_rows.append(
            f"""
            <tr>
                <td class="rank">#{row['Rank']}</td>
                <td class="pid">{row['Patient']}</td>
                <td><span class="badge-letter-custom {tier_letter}">{tier_letter}</span> {row['Queue Tier']}</td>
                <td class="num">{row['Sequence Score']}</td>
                <td class="num">{row['Current Risk']}</td>
                <td class="num">{row['60-min Risk']}</td>
                <td>{row['Confidence']}</td>
                <td>{row['Waiting']}</td>
                <td><span class="reassess {'urgent' if 'min' in row['Reassess In'] and int(row['Reassess In'].split()[0]) <= 5 else 'soon' if 'min' in row['Reassess In'] and int(row['Reassess In'].split()[0]) <= 15 else ''}">{row['Reassess In']}</span></td>
                <td>{row['Recommended Action']}</td>
                <td><b>{row['Clinician Action']}</b></td>
            </tr>
            """
        )
    
    st.markdown(
        f"""
        <div class="tbl-wrap mb-16">
            <table class="tbl">
                <thead>
                    <tr>
                        <th>Rank</th>
                        <th>Patient</th>
                        <th>Queue Tier</th>
                        <th class="th-num">Score</th>
                        <th class="th-num">Current Risk</th>
                        <th class="th-num">60m Risk</th>
                        <th>Confidence</th>
                        <th>Waiting</th>
                        <th>Reassess In</th>
                        <th>Action</th>
                        <th>Clinician Action</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(queue_rows)}
                </tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")

    # ---------------------------------------------------------
    # Recommended Resource Allocation (Milestone 5)
    # ---------------------------------------------------------
    st.markdown("### 🛏️ Recommended Resource Allocation")
    st.markdown("**Capacity-aware simulation** using queue priority and resource compatibility.")
    st.caption("⚠️ _Allocation recommendations are simulated operational support only. Final placement remains a clinician decision._")

    # Render bed allocation as Custom HTML Table
    alloc_rows = []
    for _, row in alloc_display_df.iterrows():
        alloc_rows.append(
            f"""
            <tr class="bed-row-custom">
                <td><b>{row['Bed']}</b></td>
                <td>{row['Type']}</td>
                <td class="pid">{row['Recommended Patient']}</td>
                <td>{row['Rank']}</td>
                <td class="num">{row['Score']}</td>
                <td>{row['Queue Tier']}</td>
                <td>{row['Why']}</td>
            </tr>
            """
        )

    st.markdown(
        f"""
        <div class="tbl-wrap mb-16">
            <table class="tbl">
                <thead>
                    <tr>
                        <th>Bed</th>
                        <th>Type</th>
                        <th>Patient</th>
                        <th>Rank</th>
                        <th class="th-num">Score</th>
                        <th>Queue Tier</th>
                        <th>Compatibility Rationale</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(alloc_rows)}
                </tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("#### ⏳ Patients Awaiting Capacity")
    st.caption("Simulation queue awaiting available compatible space or scheduled reassessment.")

    # Render waiting patients custom table
    waiting_rows = []
    for row in waiting_display_data:
        waiting_rows.append(
            f"""
            <tr>
                <td class="pid">{row['Patient']}</td>
                <td>{row['Rank']}</td>
                <td>{row['Queue Tier']}</td>
                <td class="num">{row['Current Risk']}</td>
                <td>{row['Reassess In']}</td>
                <td><span class="badge neutral">{row['Allocation Status']}</span></td>
            </tr>
            """
        )

    st.markdown(
        f"""
        <div class="tbl-wrap mb-16">
            <table class="tbl">
                <thead>
                    <tr>
                        <th>Patient</th>
                        <th>Rank</th>
                        <th>Queue Tier</th>
                        <th class="th-num">Current Risk</th>
                        <th>Reassessment Due</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(waiting_rows)}
                </tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True
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

    # Custom HTML Compare Table
    def format_diff_val(val, inverse=False):
        if val == 0:
            return '<span class="neutral-delta">0</span>'
        # For delays/breaches/inversions, lower is better (so negative diff is a win)
        is_win = (val < 0) if not inverse else (val > 0)
        color_class = "win" if is_win else "lose"
        sign = "+" if val > 0 else ""
        return f'<span class="{color_class}">{sign}{val}</span>'

    comp_table_html = f"""
    <div class="tbl-wrap mb-16">
        <table class="tbl compare-table">
            <thead>
                <tr>
                    <th>Operations Performance Metric</th>
                    <th>Static Baseline (ESI + FIFO)</th>
                    <th>LISA Dynamic (Risk-of-Wait)</th>
                    <th>Simulated Difference</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="metric-name">Reassessment Deadlines Breached</td>
                    <td>{static_metrics['reassessment_deadlines_missed']} ({static_metrics['reassessment_deadlines_missed_pct']}%)</td>
                    <td>{lisa_metrics['reassessment_deadlines_missed']} ({lisa_metrics['reassessment_deadlines_missed_pct']}%)</td>
                    <td>{format_diff_val(diffs['reassessment_deadline_breaches_difference'])}</td>
                </tr>
                <tr>
                    <td class="metric-name">Average Reassessment Delay</td>
                    <td>{static_metrics['average_reassessment_delay_min']} min</td>
                    <td>{lisa_metrics['average_reassessment_delay_min']} min</td>
                    <td>{format_diff_val(diffs['average_delay_difference_min'])}</td>
                </tr>
                <tr>
                    <td class="metric-name">Urgent (Tier A/B) Reviewed ≤ 15 min</td>
                    <td>{static_metrics['urgent_reviewed_within_15_min']} / {static_metrics['urgent_total']} ({static_metrics['urgent_reviewed_pct']}%)</td>
                    <td>{lisa_metrics['urgent_reviewed_within_15_min']} / {lisa_metrics['urgent_total']} ({lisa_metrics['urgent_reviewed_pct']}%)</td>
                    <td>{format_diff_val(diffs['urgent_reviewed_15min_difference'], inverse=True)}</td>
                </tr>
                <tr>
                    <td class="metric-name">High Wait-Risk Reviewed ≤ 30 min</td>
                    <td>{static_metrics['high_wait_risk_reviewed_within_30_min']} / {static_metrics['high_wait_risk_total']} ({static_metrics['high_wait_risk_reviewed_pct']}%)</td>
                    <td>{lisa_metrics['high_wait_risk_reviewed_within_30_min']} / {lisa_metrics['high_wait_risk_total']} ({lisa_metrics['high_wait_risk_reviewed_pct']}%)</td>
                    <td>{format_diff_val(diffs['high_wait_risk_reviewed_30min_difference'], inverse=True)}</td>
                </tr>
                <tr>
                    <td class="metric-name">Dynamic-Priority Inversions</td>
                    <td>{static_metrics['lower_urgency_ahead_of_urgent_count']} inversions</td>
                    <td>{lisa_metrics['lower_urgency_ahead_of_urgent_count']} inversions</td>
                    <td>{format_diff_val(diffs['priority_inversion_difference'])}</td>
                </tr>
                <tr>
                    <td class="metric-name">Protocol Floors Reviewed ≤ 5 min</td>
                    <td>{static_metrics['protocol_floor_reviewed_within_5_min']} / {static_metrics['protocol_floor_total']}</td>
                    <td>{lisa_metrics['protocol_floor_reviewed_within_5_min']} / {lisa_metrics['protocol_floor_total']}</td>
                    <td>{format_diff_val(diffs['protocol_floor_reviewed_5min_difference'], inverse=True)}</td>
                </tr>
            </tbody>
        </table>
    </div>
    """
    st.markdown(comp_table_html, unsafe_allow_html=True)

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
        st.write(f"- **Initial Clinician Triage:** Level {patient['initial_triage_level']}")
        st.write(f"- **Mental Status:** {patient['mental_status']}")
        st.write(f"- **Visible Distress:** {patient['visible_distress']}")
        st.write(f"- **Pain Score:** {patient['pain_score']} / 10")

    with info_col3:
        st.markdown("**Records & Resources**")
        st.write(f"- **Prior Records Available:** {patient['prior_record_available']}")
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
        
        rules_html = "".join([f"<li>Rule <b>{r_id}</b> — {reason}</li>" for r_id, reason in zip(patient_floor["rule_ids"], patient_floor["reasons"])])
        
        guardrail_html = f"""
        <div class="safety-floor mb-16">
            <div class="lock">🔒</div>
            <div class="txt">
                <div class="title">Hard Protocol Safety Floor Level {floor_lvl} Triggered ({urgency_label})</div>
                <div class="desc">Locked minimum priority level. Queue Sequencer cannot prioritize this patient below Tier {'A' if floor_lvl == 1 else 'B'}.</div>
            </div>
        </div>
        <div class="card-custom mb-16">
            <div class="card-custom-title">🔒 Triggered Protocol Guardrail Rules</div>
            <ul class="list-tick-custom">
                {rules_html}
            </ul>
        </div>
        """
        st.markdown(guardrail_html, unsafe_allow_html=True)
    else:
        st.markdown(
            """
            <div class="alert success mb-16">
                <span>✓ <b>Protocol Floor:</b> No hard physiological floor triggered. Priority is dynamically determined by Risk-of-Wait trajectory.</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Risk of Waiting Section (Milestone 3)
    # ---------------------------------------------------------
    st.markdown("---")
    st.markdown("### ⏱️ Risk of Waiting")

    has_hard_floor = patient_floor["triggered"] and patient_floor["floor_level"] in [1, 2]

    # Protocol Floor Priority Banner over Breach Clock
    if has_hard_floor:
        st.markdown(
            f"""
            <div class="alert danger mb-16">
                <span>🚨 <b>Protocol Floor Active (Level {patient_floor['floor_level']}):</b> Hard safety guardrail takes precedence over waiting projections. Reassessment Due: <b>{patient_risk['recheck_due_min']} min</b></span>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Risk Breach Clock display logic
    if has_hard_floor and patient_risk["time_to_breach_min"] != 0:
        breach_val = "Secondary"
    elif patient_risk["time_to_breach_min"] == 0:
        breach_val = "⚠️ Breached"
    elif patient_risk["time_to_breach_min"] is not None:
        breach_val = f"~{patient_risk['time_to_breach_min']} min"
    else:
        breach_val = ">120 min"

    st.markdown(
        f"""
        <div class="grid-4 mb-16">
            <div class="kpi-card-custom accent">
                <div class="label-custom">Current Wait Risk</div>
                <div class="value-custom">{patient_risk['current_risk']} <span class="text-xs">/ 100</span></div>
                <div class="desc-custom">Band: {patient_risk['risk_band']}</div>
            </div>
            <div class="kpi-card-custom">
                <div class="label-custom">60 min Projected</div>
                <div class="value-custom">{patient_risk['risk_60_min']} <span class="text-xs">/ 100</span></div>
                <div class="desc-custom">30m: {patient_risk['risk_30_min']} | 120m: {patient_risk['risk_120_min']}</div>
            </div>
            <div class="kpi-card-custom">
                <div class="label-custom">Risk Breach Clock</div>
                <div class="value-custom">{breach_val}</div>
                <div class="desc-custom">Confidence: {patient_risk['confidence']}%</div>
            </div>
            <div class="kpi-card-custom urgent">
                <div class="label-custom">Reassessment Due</div>
                <div class="value-custom">{patient_risk['recheck_due_min']} <span class="text-xs">min</span></div>
                <div class="desc-custom">Simulated reassessment window</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

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

    init_lvl = patient_ranked.get("initial_triage_level")
    proto_lvl = patient_ranked.get("protocol_floor_level")
    eff_floor = patient_ranked.get("effective_safety_floor")
    eff_src = patient_ranked.get("effective_safety_floor_source")

    if eff_floor:
        if eff_src == "CLINICIAN_TRIAGE":
            eff_label = f"Level {eff_floor} (Clinician precedence)"
        elif eff_src == "PROTOCOL_GUARDRAIL":
            eff_label = f"Level {eff_floor} (Protocol guardrail)"
        elif eff_src == "BOTH":
            eff_label = f"Level {eff_floor} (Concordant)"
        else:
            eff_label = f"Level {eff_floor}"
    else:
        eff_label = "No safety floor active"

    st.markdown(
        f"""
        <div class="grid-4 mb-16">
            <div class="kpi-card-custom accent">
                <div class="label-custom">Priority Rank</div>
                <div class="value-custom">#{patient_ranked['priority_rank']} <span class="text-xs">/ {total_patients}</span></div>
                <div class="desc-custom">Effective Score: {patient_ranked['sequence_score']}</div>
            </div>
            <div class="kpi-card-custom">
                <div class="label-custom">Queue Tier</div>
                <div class="value-custom">{patient_ranked['queue_tier']}</div>
                <div class="desc-custom">Safety Floor: {eff_label}</div>
            </div>
            <div class="kpi-card-custom">
                <div class="label-custom">Initial Clinician Triage</div>
                <div class="value-custom">Level {init_lvl if init_lvl else '—'}</div>
                <div class="desc-custom">Triage input</div>
            </div>
            <div class="kpi-card-custom">
                <div class="label-custom">Recommended Action</div>
                <div class="value-custom" style="font-size: 16px; font-weight:700; margin-top:8px;">{patient_ranked['recommended_queue_action']}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("#### 🔍 Why this patient is prioritized here:")
    reasons_html = "".join([f"<li>{reason}</li>" for reason in patient_ranked["sequence_reasons"]])
    st.markdown(f"<ul class='list-tick-custom mb-16'>{reasons_html}</ul>", unsafe_allow_html=True)

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

    if patient_alloc["allocation_status"] == STATUS_ALLOCATED:
        alloc_status_label = "✅ Allocated"
        alloc_detail = f"{patient_alloc['bed_id']} — {patient_alloc['bed_type']}"
        alloc_note = f"Minimum Resource Need: {patient_alloc['minimum_resource_level']}"
        alloc_alert_class = "success"
    else:
        alloc_status_label = f"⏳ {patient_alloc['allocation_status']}"
        alloc_detail = " / ".join(patient_alloc["preferred_bed_types"])
        alloc_note = f"Reassessment Deadline: {patient_alloc['recheck_due_min']} min"
        alloc_alert_class = "warn"

    st.markdown(
        f"""
        <div class="grid-3 mb-16">
            <div class="kpi-card-custom">
                <div class="label-custom">Allocation Status</div>
                <div class="value-custom">{alloc_status_label}</div>
            </div>
            <div class="kpi-card-custom">
                <div class="label-custom">Target Bed / Types</div>
                <div class="value-custom" style="font-size:16px; font-weight:700; margin-top:8px;">{alloc_detail}</div>
            </div>
            <div class="kpi-card-custom">
                <div class="label-custom">Operational Constraint</div>
                <div class="value-custom" style="font-size:14px; font-weight:700; margin-top:10px;">{alloc_note}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        f"""
        <div class="alert {alloc_alert_class} mb-16">
            <span><b>Allocation Output:</b> {patient_alloc['allocation_reason']}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("#### 🔍 Clinical Compatibility Profile:")
    alloc_reasons_html = "".join([f"<li>{reason}</li>" for reason in patient_alloc["allocation_reasons"]])
    st.markdown(f"<ul class='list-tick-custom mb-16'>{alloc_reasons_html}</ul>", unsafe_allow_html=True)

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

    # System vs Clinician state formatted as a split card
    if latest_p_action:
        act_type = latest_p_action["action"]
        if act_type == ACTION_ACCEPT:
            clin_state_html = f"✅ Accepted ({latest_p_action['clinician_selected_tier']})"
        elif act_type == ACTION_OVERRIDE:
            clin_state_html = f"⚠️ Override Active ({latest_p_action['clinician_selected_tier']})<br/><small style='font-size:11px; font-weight:normal;'>Reason: {latest_p_action['override_reason']}</small>"
        elif act_type == ACTION_ESCALATE:
            clin_state_html = f"⚡ Escalated ({latest_p_action['clinician_selected_tier']})"
        else:
            clin_state_html = "—"
    else:
        clin_state_html = "<i>System recommendation active</i>"

    split_card_html = f"""
    <div class="decision-split-custom mb-16">
        <div class="sys-panel">
            <div class="panel-label">System Recommendation</div>
            <div class="panel-value">{patient_ranked['queue_tier']}</div>
            <div style="font-size:11px; color:var(--muted); margin-top:4px;">Score: <b>{patient_ranked['sequence_score']} / 100</b></div>
        </div>
        <div class="clinician-panel">
            <div class="panel-label">Your Decision State</div>
            <div class="panel-value">{clin_state_html}</div>
        </div>
    </div>
    """
    st.markdown(split_card_html, unsafe_allow_html=True)

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
            audit_rows.append(
                f"""
                <tr>
                    <td>{e['timestamp']}</td>
                    <td class="pid">{e['patient_token']}</td>
                    <td><b>{e['action']}</b></td>
                    <td>{e['system_queue_tier']}</td>
                    <td>{e['clinician_selected_tier'] or '—'}</td>
                    <td class="num">{e['system_sequence_score']}</td>
                    <td>{e['override_reason'] or '—'}</td>
                    <td><code class="mono-custom">{e['model_version']}</code></td>
                    <td><code class="mono-custom">{e['rule_version']}</code></td>
                </tr>
                """
            )
        
        st.markdown(
            f"""
            <div class="tbl-wrap mb-16">
                <table class="tbl">
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Patient</th>
                            <th>Action</th>
                            <th>Sys Tier</th>
                            <th>Clin Tier</th>
                            <th class="th-num">Score</th>
                            <th>Override Reason</th>
                            <th>Model</th>
                            <th>Rules</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(audit_rows)}
                    </tbody>
                </table>
            </div>
            """,
            unsafe_allow_html=True
        )

        with st.expander("🔍 Inspect Full Audit Event Payloads", expanded=False):
            for i, e in enumerate(reversed(events), start=1):
                st.markdown(f"**Event #{event_count - i + 1} — {e['patient_token']} ({e['action']}) at {e['timestamp']}**")
                st.json(e)
    else:
        st.markdown(
            """
            <div class="alert info mb-16">
                <span>No clinician actions logged in this session yet. Use the Patient Inspector to accept, escalate, or override recommendations.</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    # ---------------------------------------------------------
    # Tab 2: Privacy, Safety & Governance Specification (Milestone 8)
    # ---------------------------------------------------------
with tab_gov:
    gov = get_governance_summary()
    st.markdown("## 🛡️ Privacy, Safety & Governance Specification")
    st.markdown(
        textwrap.dedent(f"""
        <div class="governance-hero-custom">
            <h3>🛡️ Clinician-controlled. Deterministic where it counts.</h3>
            <p>LISA.ai is an ED operations and sequencing tool. It surfaces <b>who should be reassessed next</b> given protocol guardrails, Risk-of-Wait trajectory and reassessment cadence — never a diagnosis, treatment, or triage substitute. Every recommendation is subordinate to clinician-entered safety floors and logged with reason codes.</p>
            <div class="principles-grid">
                <div class="principle-item"><span class="dot"></span>Human-in-the-loop by default</div>
                <div class="principle-item"><span class="dot"></span>Deterministic protocol floors</div>
                <div class="principle-item"><span class="dot"></span>Explainable reason codes</div>
                <div class="principle-item"><span class="dot"></span>Tokenized synthetic data only</div>
                <div class="principle-item"><span class="dot"></span>No diagnostic language</div>
                <div class="principle-item"><span class="dot"></span>Session-scoped audit trail</div>
            </div>
        </div>
        """),
        unsafe_allow_html=True
    )

    # Implemented vs Required Grid
    st.markdown("### Implemented Safeguards vs Production Requirements")
    st.caption("A side-by-side verification of what controls exist in the active prototype and what would be required in a production hospital setting.")

    impl_items = "".join([f"<li>{item}</li>" for item in gov["implemented_prototype_controls"]])
    impl_panel = f"""
    <div class="gov-panel-custom impl">
        <div class="panel-header-custom">
            <h4>Implemented in Prototype</h4>
            <span class="badge-custom">Prototype Implemented</span>
        </div>
        <ul>
            {impl_items}
        </ul>
    </div>
    """

    req_items = "".join([f"<li>{item}</li>" for item in gov["unimplemented_production_requirements"]])
    req_panel = f"""
    <div class="gov-panel-custom req">
        <div class="panel-header-custom">
            <h4>Production Deployment Requirements</h4>
            <span class="badge-custom">Production Requirement</span>
        </div>
        <ul>
            {req_items}
        </ul>
    </div>
    """

    # Render side-by-side using columns
    gov_col1, gov_col2 = st.columns(2)
    with gov_col1:
        st.markdown(textwrap.dedent(impl_panel), unsafe_allow_html=True)
    with gov_col2:
        st.markdown(textwrap.dedent(req_panel), unsafe_allow_html=True)

    st.markdown("---")

    # Excluded Features (Anti-Bias Invariant)
    st.markdown("### 🚫 Excluded Prioritization Features (Anti-Bias Invariant)")
    st.markdown(
        "To prevent socioeconomic, financial, and institutional bias, the following features are **strictly excluded** "
        "from clinical protocol rules, Risk-of-Wait scoring, queue sequencing, and bed allocation:"
    )

    ex_items_html = "".join([f'<div class="excluded-item-custom"><span class="strike-custom">✗</span> {feat.replace("_", " ").title()}</div>' for feat in gov["excluded_prioritization_features"]])
    st.markdown(textwrap.dedent(f'<div class="excluded-grid-custom">{ex_items_html}</div>'), unsafe_allow_html=True)

    st.markdown("---")

    # Data Minimization & Version Governance
    st.markdown("### 🔒 Data Minimization & Version Governance")
    dm_col1, dm_col2 = st.columns(2)
    with dm_col1:
        st.markdown("**Data Minimization Rules:**")
        for rule in gov["data_minimization_rules"]:
            st.markdown(f"- {rule}")
    with dm_col2:
        st.markdown("**Model & Rule Version Registry:**")
        ver_rows = []
        for v in gov["model_and_rule_versions"]:
            ver_rows.append(f"<li>{v['component']}: <code class='mono-custom'>{v['version']}</code></li>")
        st.markdown(textwrap.dedent(f"<ul class='list-tick-custom'>{''.join(ver_rows)}</ul>"), unsafe_allow_html=True)

    st.markdown("---")

    # Fairness & Regulatory Assumptions
    st.markdown("### 🌐 Fairness & Jurisdiction Assumptions")
    
    # Fairness monitored details
    st.markdown("**Fairness Subgroup Monitoring Plan:**")
    st.caption("Production validation requires continuous performance disparity monitoring across:")
    fairness_items = "".join([f"<li>{dim}</li>" for dim in gov["fairness_monitoring_dimensions"]])
    st.markdown(textwrap.dedent(f"<ul class='list-tick-custom mb-16'>{fairness_items}</ul>"), unsafe_allow_html=True)

    reg = gov["regulatory_design_assumptions"]
    reg_col1, reg_col2 = st.columns(2)
    with reg_col1:
        st.markdown("#### 🇮🇳 India Deployment Focus")
        st.write(f"**Framework Reference:** {reg['india_focus']['frameworks']}")
        st.caption(f"⚠️ {reg['india_focus']['disclaimer']}")
    with reg_col2:
        st.markdown("#### 🌍 International Expansion")
        st.write(f"**Framework Reference:** {reg['international_expansion']['frameworks']}")
        st.caption(f"⚠️ {reg['international_expansion']['disclaimer']}")

    st.markdown("---")

    # 9. End-to-End Data Flow
    st.markdown("### 9. 🔄 End-to-End Decision Flow")
    st.code(" → ".join(gov["data_flow_steps"]), language="text")
    st.caption("🔒 _Synthetic environment only — no real patient data is ingested, processed, or transmitted._")
